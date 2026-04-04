from dataclasses import dataclass, field

from pydantic import BaseModel

from interviewd.adapters.llm.base import LLMAdapter
from interviewd.engine.interview import InterviewSession, Turn


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class AnswerScore(BaseModel):
    """Scores for a single question–answer pair."""

    question_id: str
    question_text: str
    answer: str
    star_score: int        # 0–10: Situation/Task/Action/Result completeness
    relevance_score: int   # 0–10: How well the answer addresses the question
    clarity_score: int     # 0–10: Communication quality and conciseness
    feedback: str          # One or two sentences of actionable feedback

    @property
    def overall(self) -> float:
        """Weighted average: relevance 40%, STAR 40%, clarity 20%."""
        return round(
            self.relevance_score * 0.4 + self.star_score * 0.4 + self.clarity_score * 0.2,
            1,
        )


@dataclass
class ScoreReport:
    """Aggregated scoring result for a full interview session."""

    scores: list[AnswerScore] = field(default_factory=list)
    summary: str = ""

    @property
    def average_overall(self) -> float:
        if not self.scores:
            return 0.0
        return round(sum(s.overall for s in self.scores) / len(self.scores), 1)

    @property
    def average_star(self) -> float:
        if not self.scores:
            return 0.0
        return round(sum(s.star_score for s in self.scores) / len(self.scores), 1)

    @property
    def average_relevance(self) -> float:
        if not self.scores:
            return 0.0
        return round(sum(s.relevance_score for s in self.scores) / len(self.scores), 1)

    @property
    def average_clarity(self) -> float:
        if not self.scores:
            return 0.0
        return round(sum(s.clarity_score for s in self.scores) / len(self.scores), 1)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SCORE_PROMPT = """\
You are an expert interviewer evaluating a candidate's answer to a behavioral interview question.

Question: {question}
Answer: {answer}

Score the answer on three dimensions (0–10 each):
- star_score: How completely the answer follows the STAR format \
(Situation, Task, Action, Result). 0 = no structure, 10 = all four parts clear and specific.
- relevance_score: How directly the answer addresses the question asked. \
0 = completely off-topic, 10 = perfectly on-point.
- clarity_score: Communication quality — clear, concise, and easy to follow. \
0 = incoherent, 10 = exceptionally clear.

Also write one or two sentences of actionable feedback the candidate can use to improve.

Respond in this exact JSON format with no extra text:
{{
  "star_score": <int 0-10>,
  "relevance_score": <int 0-10>,
  "clarity_score": <int 0-10>,
  "feedback": "<string>"
}}"""

_SUMMARY_PROMPT = """\
You are an expert interviewer. Here are the scores from a mock behavioral interview:

{score_lines}

Overall average: {average}/10

Write 2–3 sentences summarising the candidate's performance. \
Highlight their strongest area and the one area that would most improve their score. \
Be encouraging but honest. Plain text only — no markdown."""


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class Scorer:
    """Scores an InterviewSession using an LLM as judge.

    Each answer is scored on STAR completeness, relevance, and clarity (0–10).
    A final summary is generated from the aggregate scores.

    Usage::

        scorer = Scorer(llm_adapter)
        report = await scorer.score(session)
    """

    def __init__(self, llm: LLMAdapter):
        self._llm = llm

    async def _score_turn(self, turn: Turn) -> AnswerScore:
        """Score a single turn (main answer; follow-up answer appended if present)."""
        full_answer = turn.answer
        if turn.follow_up_asked and turn.follow_up_answer:
            full_answer = f"{turn.answer}\n\nFollow-up: {turn.follow_up_answer}"

        prompt = _SCORE_PROMPT.format(
            question=turn.question.text,
            answer=full_answer,
        )
        raw = await self._llm.complete([{"role": "user", "content": prompt}], stream=False)

        scores = _parse_scores(raw)
        return AnswerScore(
            question_id=turn.question.id,
            question_text=turn.question.text,
            answer=full_answer,
            **scores,
        )

    async def score(self, session: InterviewSession) -> ScoreReport:
        """Score all turns in the session and return a ScoreReport.

        Args:
            session: Completed InterviewSession from InterviewEngine.run().

        Returns:
            ScoreReport with per-turn AnswerScore objects and an overall summary.
        """
        answer_scores: list[AnswerScore] = []
        for turn in session.turns:
            answer_scores.append(await self._score_turn(turn))

        report = ScoreReport(scores=answer_scores)

        score_lines = "\n".join(
            f"Q{i + 1} ({s.question_id}): STAR={s.star_score}, "
            f"Relevance={s.relevance_score}, Clarity={s.clarity_score} → {s.overall}/10"
            for i, s in enumerate(answer_scores)
        )
        summary_prompt = _SUMMARY_PROMPT.format(
            score_lines=score_lines,
            average=report.average_overall,
        )
        report.summary = await self._llm.complete(
            [{"role": "user", "content": summary_prompt}], stream=False
        )
        return report


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _parse_scores(raw: str) -> dict:
    """Extract star/relevance/clarity/feedback from the LLM JSON response.

    Lenient: strips markdown code fences and falls back to 0/empty on parse
    failure so a single bad LLM response doesn't crash the whole session.
    """
    import json
    import re

    # Strip ```json ... ``` fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    try:
        data = json.loads(cleaned)
        return {
            "star_score": int(data.get("star_score", 0)),
            "relevance_score": int(data.get("relevance_score", 0)),
            "clarity_score": int(data.get("clarity_score", 0)),
            "feedback": str(data.get("feedback", "")),
        }
    except (json.JSONDecodeError, ValueError):
        return {"star_score": 0, "relevance_score": 0, "clarity_score": 0, "feedback": ""}
