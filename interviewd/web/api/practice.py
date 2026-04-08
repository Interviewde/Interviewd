"""Practice mode API.

Practice sessions let candidates drill individual questions from a plan with
full free-form conversation — the agent responds to clarifying questions, asks
follow-ups, and coaches throughout. Sessions are not scored or persisted.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from interviewd.data.question_bank import Question
from interviewd.web import practice_state as store
from interviewd.web.adapters import ensure_adapters

router = APIRouter(prefix="/api/practice", tags=["practice"])


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_COACH_PROMPT = """\
You are an interview coach helping a candidate practice for a real interview.

The question being practiced:
"{question_text}"

Conversation so far:
{history_text}

The candidate just said:
"{transcript}"

Respond as a coach in 1-3 concise sentences:
- If they are asking a clarifying question, provide specific realistic context \
(numbers, scale, constraints, environment).
- If their answer is shallow or misses important aspects, ask a targeted \
follow-up to probe deeper.
- If they gave a solid answer, briefly acknowledge it and probe one more angle \
that hasn't been covered yet.
- Do NOT repeat their answer back verbatim.
- Stay focused only on this question.
- Never suggest moving to the next question — the candidate controls when to advance."""


def _build_history_text(history: list[dict]) -> str:
    if not history:
        return "(no conversation yet)"
    lines = []
    for turn in history:
        role = "Coach" if turn["role"] == "agent" else "Candidate"
        lines.append(f"{role}: {turn['text']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class PracticeStartRequest(BaseModel):
    question_ids: list[str]
    plan_id: str | None = None
    plan_data: dict | None = None


class PracticeQuestionDetail(BaseModel):
    id: str
    text: str
    tags: list[str] = []
    difficulty: str
    rationale: str = ""


class PracticeStartResponse(BaseModel):
    session_id: str
    question: PracticeQuestionDetail
    index: int
    total: int


class PracticeAnswerResponse(BaseModel):
    agent_text: str
    transcript: str


class PracticeNextResponse(BaseModel):
    status: str  # "next_question" | "complete"
    question: PracticeQuestionDetail | None = None
    index: int | None = None
    total: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_questions_from_plan(
    plan_id: str | None, plan_data: dict | None
) -> list[Question]:
    """Load all questions from a standard plan id or a generated plan dict."""
    if plan_data is not None:
        from interviewd.planner.models import InterviewPlan

        try:
            plan = InterviewPlan.model_validate(plan_data)
        except Exception as exc:
            raise HTTPException(400, f"Invalid plan data: {exc}")
        return plan.to_questions()

    if plan_id is not None:
        from interviewd.planner.models import InterviewPlan

        plan_path = Path("config/plans") / f"{plan_id}.yaml"
        if not plan_path.exists():
            raise HTTPException(404, f"Standard plan '{plan_id}' not found.")
        try:
            plan = InterviewPlan.from_yaml(str(plan_path))
        except Exception as exc:
            raise HTTPException(400, f"Could not load plan: {exc}")
        return plan.to_questions()

    raise HTTPException(400, "Provide either plan_id or plan_data.")


def _to_detail(q: Question, rationale: str = "") -> PracticeQuestionDetail:
    return PracticeQuestionDetail(
        id=q.id,
        text=q.text,
        tags=q.tags,
        difficulty=q.difficulty,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start", response_model=PracticeStartResponse)
async def start_practice(body: PracticeStartRequest, request: Request):
    """Create a practice session for the selected question ids."""
    try:
        ensure_adapters(request.app.state)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    if not body.question_ids:
        raise HTTPException(400, "Select at least one question to practice.")

    all_questions = _load_questions_from_plan(body.plan_id, body.plan_data)

    # Preserve the order the user selected
    by_id = {q.id: q for q in all_questions}
    selected = [by_id[qid] for qid in body.question_ids if qid in by_id]
    if not selected:
        raise HTTPException(400, "None of the provided question_ids were found in the plan.")

    session_id = str(uuid.uuid4())
    state = store.PracticeSessionState(questions=selected)
    store.create(session_id, state)

    first_q = selected[0]
    return PracticeStartResponse(
        session_id=session_id,
        question=_to_detail(first_q),
        index=0,
        total=len(selected),
    )


@router.post("/{session_id}/answer", response_model=PracticeAnswerResponse)
async def practice_answer(
    session_id: str,
    request: Request,
    audio: UploadFile = File(...),
):
    """Receive candidate audio, transcribe it, and return the coach's response."""
    try:
        ensure_adapters(request.app.state)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    state = store.get(session_id)
    if state is None:
        raise HTTPException(404, "Practice session not found or expired.")

    stt = request.app.state.stt
    llm = request.app.state.llm

    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/webm"
    filename = "audio.webm" if "webm" in content_type else "audio.wav"
    transcript = await stt.transcribe(audio_bytes, filename=filename)

    # Append candidate turn to history
    state.history.append({"role": "user", "text": transcript})

    current_q = state.questions[state.current_idx]
    history_text = _build_history_text(state.history[:-1])  # exclude the just-added turn

    prompt = _COACH_PROMPT.format(
        question_text=current_q.text,
        history_text=history_text,
        transcript=transcript,
    )
    agent_text = await llm.complete([{"role": "user", "content": prompt}], stream=False)
    agent_text = agent_text.strip()

    # Append agent turn to history
    state.history.append({"role": "agent", "text": agent_text})

    return PracticeAnswerResponse(agent_text=agent_text, transcript=transcript)


@router.post("/{session_id}/next", response_model=PracticeNextResponse)
async def practice_next(session_id: str):
    """Advance to the next question, or signal completion."""
    state = store.get(session_id)
    if state is None:
        raise HTTPException(404, "Practice session not found or expired.")

    state.current_idx += 1
    state.history = []  # fresh conversation for the next question

    if state.current_idx >= len(state.questions):
        store.remove(session_id)
        return PracticeNextResponse(status="complete")

    next_q = state.questions[state.current_idx]
    return PracticeNextResponse(
        status="next_question",
        question=_to_detail(next_q),
        index=state.current_idx,
        total=len(state.questions),
    )
