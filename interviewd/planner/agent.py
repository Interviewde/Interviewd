"""JD + Resume planner agent.

Two-step LLM pipeline:
  1. Analyse job description and resume → extract required skills and gaps.
  2. Generate a tailored question list weighted toward the identified gaps.

Usage::

    from interviewd.adapters.llm.registry import get_llm_adapter
    from interviewd.config import load_settings
    from interviewd.planner.agent import PlannerAgent

    settings = load_settings()
    llm = get_llm_adapter(settings.llm)
    agent = PlannerAgent(llm)
    plan = await agent.run(
        jd_text, resume_text,
        interview_type="technical",
        difficulty="senior",
        num_questions=5,
        jd_source="job.pdf",
        resume_source="resume.pdf",
    )
"""

import json
import re
from datetime import datetime, timezone

from interviewd.adapters.llm.base import LLMAdapter
from interviewd.planner.models import (
    InterviewPlan,
    PlannedQuestion,
    SkillGap,
    SkillsAnalysis,
)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_ANALYSIS_PROMPT = """\
You are a senior technical recruiter and interview strategist.

Analyse the job description and resume below, then return a JSON object (no markdown, no extra text).

Job Description:
{jd_text}

---

Resume:
{resume_text}

---

Output format:
{{
  "required_skills": ["<skill1>", "<skill2>", ...],
  "skill_gaps": [
    {{
      "skill": "<skill name>",
      "required_level": "high" | "medium" | "low",
      "resume_level": "strong" | "partial" | "missing"
    }},
    ...
  ],
  "summary": "<2-3 sentences: candidate strengths and key gaps relevant to this role>"
}}

Rules:
- required_skills: top 6-10 skills the JD demands
- skill_gaps: only include skills where resume_level is "partial" or "missing"
- Be specific with skill names (e.g. "Kubernetes" not "DevOps")
- summary must be plain text, no markdown"""

_PLANNING_PROMPT = """\
You are a senior technical interviewer designing a tailored mock interview.

Candidate profile:
{skills_json}

Interview parameters:
- Type: {interview_type}
- Difficulty: {difficulty}
- Number of questions: {num_questions}

Generate exactly {num_questions} interview questions. Weight the questions toward \
the candidate's skill gaps while still covering their strengths.

Return a JSON object (no markdown, no extra text):
{{
  "questions": [
    {{
      "id": "plan_001",
      "text": "<the interview question>",
      "tags": ["<tag1>", "<tag2>"],
      "difficulty": "entry" | "mid" | "senior" | "staff",
      "follow_up": "<a natural follow-up question>",
      "rationale": "<one sentence: why this question given the JD/resume analysis>"
    }},
    ...
  ]
}}

Rules:
- id values must be plan_001, plan_002, ... (zero-padded to 3 digits)
- difficulty should match the requested level or one step lower for gap areas
- follow_up must be a genuine probing question, not a restatement
- rationale is for internal use; be specific about JD/resume evidence"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class PlannerAgent:
    """Two-step LLM agent that produces a tailored InterviewPlan."""

    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    async def run(
        self,
        jd_text: str,
        resume_text: str,
        interview_type: str,
        difficulty: str,
        num_questions: int,
        jd_source: str = "",
        resume_source: str = "",
    ) -> InterviewPlan:
        """Analyse documents and generate a question plan.

        Args:
            jd_text: Plain text of the job description.
            resume_text: Plain text of the resume / CV.
            interview_type: One of behavioral | technical | hr | system_design.
            difficulty: One of entry | mid | senior | staff.
            num_questions: How many questions to generate.
            jd_source: Original file path, stored in plan metadata.
            resume_source: Original file path, stored in plan metadata.

        Returns:
            A validated InterviewPlan ready for serialisation.
        """
        analysis = await self._analyse(jd_text, resume_text)
        questions = await self._generate_questions(
            analysis, interview_type, difficulty, num_questions
        )

        return InterviewPlan(
            generated_at=datetime.now(timezone.utc).isoformat(),
            jd_source=jd_source,
            resume_source=resume_source,
            interview_type=interview_type,  # type: ignore[arg-type]
            difficulty=difficulty,  # type: ignore[arg-type]
            num_questions=num_questions,
            skills_analysis=analysis,
            questions=questions,
        )

    async def _analyse(self, jd_text: str, resume_text: str) -> SkillsAnalysis:
        prompt = _ANALYSIS_PROMPT.format(
            jd_text=jd_text[:4000],
            resume_text=resume_text[:3000],
        )
        raw = await self._llm.complete(
            [{"role": "user", "content": prompt}], stream=False
        )
        data = _parse_json(raw)
        return SkillsAnalysis(
            required_skills=data.get("required_skills", []),
            skill_gaps=[SkillGap(**g) for g in data.get("skill_gaps", [])],
            summary=data.get("summary", ""),
        )

    async def _generate_questions(
        self,
        analysis: SkillsAnalysis,
        interview_type: str,
        difficulty: str,
        num_questions: int,
    ) -> list[PlannedQuestion]:
        prompt = _PLANNING_PROMPT.format(
            skills_json=analysis.model_dump_json(indent=2),
            interview_type=interview_type,
            difficulty=difficulty,
            num_questions=num_questions,
        )
        raw = await self._llm.complete(
            [{"role": "user", "content": prompt}], stream=False
        )
        data = _parse_json(raw)
        return [PlannedQuestion(**q) for q in data.get("questions", [])]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON; returns empty dict on failure."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {}
