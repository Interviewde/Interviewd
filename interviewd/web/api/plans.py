"""Plans API — list standard plans and generate a personalised plan from JD + resume."""

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/api/plans", tags=["plans"])

_PLANS_DIR = Path("config/plans")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class PlanMeta(BaseModel):
    id: str
    title: str
    interview_type: str
    difficulty: str
    num_questions: int
    summary: str


class SkillGapOut(BaseModel):
    skill: str
    required_level: str
    resume_level: str


class SkillsAnalysisOut(BaseModel):
    required_skills: list[str]
    skill_gaps: list[SkillGapOut]
    summary: str


class PlannedQuestionOut(BaseModel):
    id: str
    text: str
    tags: list[str]
    difficulty: str
    follow_up: str
    rationale: str


class GeneratedPlan(BaseModel):
    generated_at: str
    jd_source: str
    resume_source: str
    interview_type: str
    difficulty: str
    num_questions: int
    time_limit_per_question: int
    persona: str
    language: str
    skills_analysis: SkillsAnalysisOut
    questions: list[PlannedQuestionOut]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan_title(stem: str) -> str:
    """'swe_technical_senior' → 'Swe Technical Senior'"""
    return stem.replace("_", " ").title()


def _load_plan_meta(path: Path) -> PlanMeta:
    import yaml

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    summary = data.get("skills_analysis", {}).get("summary", "")
    # YAML may load summary as a multiline scalar — flatten to one line
    summary = " ".join(str(summary).split())

    return PlanMeta(
        id=path.stem,
        title=_plan_title(path.stem),
        interview_type=data.get("interview_type", ""),
        difficulty=data.get("difficulty", ""),
        num_questions=data.get("num_questions", 0),
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[PlanMeta])
def list_plans() -> list[PlanMeta]:
    """Return metadata for all standard plans in config/plans/."""
    if not _PLANS_DIR.exists():
        return []
    plans = []
    for path in sorted(_PLANS_DIR.glob("*.yaml")):
        try:
            plans.append(_load_plan_meta(path))
        except Exception:
            pass  # skip malformed files
    return plans


@router.post("/generate", response_model=GeneratedPlan)
async def generate_plan(
    request: Request,
    jd_file: UploadFile = File(..., description="Job description (.pdf, .txt, .md)"),
    resume_file: UploadFile = File(..., description="Resume / CV (.pdf, .txt, .md)"),
    interview_type: str = Form("technical"),
    difficulty: str = Form("mid"),
    num_questions: int = Form(5),
) -> GeneratedPlan:
    """Upload JD + resume files, run the planner agent, return a plan.

    The plan is returned in the response — it is not persisted server-side.
    The browser holds it in state and passes it to POST /api/interview/start.
    """
    from interviewd.planner.agent import PlannerAgent
    from interviewd.planner.ingestion import extract_text
    from interviewd.web.adapters import ensure_adapters

    _VALID_TYPES = ("behavioral", "technical", "hr", "system_design")
    _VALID_DIFFICULTIES = ("entry", "mid", "senior", "staff")

    if interview_type not in _VALID_TYPES:
        raise HTTPException(400, f"Invalid type '{interview_type}'.")
    if difficulty not in _VALID_DIFFICULTIES:
        raise HTTPException(400, f"Invalid difficulty '{difficulty}'.")
    if not (1 <= num_questions <= 10):
        raise HTTPException(400, "num_questions must be between 1 and 10.")

    try:
        ensure_adapters(request.app.state)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    # Write uploaded files to temp paths so ingestion can detect extension
    import tempfile

    jd_bytes = await jd_file.read()
    resume_bytes = await resume_file.read()

    jd_suffix = Path(jd_file.filename or "jd.txt").suffix or ".txt"
    resume_suffix = Path(resume_file.filename or "resume.txt").suffix or ".txt"

    with (
        tempfile.NamedTemporaryFile(suffix=jd_suffix, delete=False) as jd_tmp,
        tempfile.NamedTemporaryFile(suffix=resume_suffix, delete=False) as resume_tmp,
    ):
        jd_tmp.write(jd_bytes)
        resume_tmp.write(resume_bytes)
        jd_tmp_path = jd_tmp.name
        resume_tmp_path = resume_tmp.name

    try:
        jd_text = extract_text(jd_tmp_path)
        resume_text = extract_text(resume_tmp_path)
    except (ValueError, ImportError) as exc:
        raise HTTPException(400, str(exc))
    finally:
        Path(jd_tmp_path).unlink(missing_ok=True)
        Path(resume_tmp_path).unlink(missing_ok=True)

    llm = request.app.state.llm
    agent = PlannerAgent(llm)

    try:
        plan = await agent.run(
            jd_text=jd_text,
            resume_text=resume_text,
            interview_type=interview_type,
            difficulty=difficulty,
            num_questions=num_questions,
            jd_source=jd_file.filename or "",
            resume_source=resume_file.filename or "",
        )
    except Exception as exc:
        raise HTTPException(500, f"Plan generation failed: {exc}")

    return GeneratedPlan(**plan.model_dump())
