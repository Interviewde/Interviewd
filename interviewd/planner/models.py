from typing import Literal

from pydantic import BaseModel

from interviewd.data.question_bank import DifficultyLevel, Question

InterviewType = Literal["behavioral", "technical", "hr", "system_design"]
PersonaType = Literal["friendly", "neutral", "adversarial"]
SkillLevel = Literal["high", "medium", "low"]
ResumeMatchLevel = Literal["strong", "partial", "missing"]


class PlannedQuestion(BaseModel):
    id: str
    text: str
    tags: list[str] = []
    difficulty: DifficultyLevel
    follow_up: str = ""
    rationale: str = ""

    def to_question(self) -> Question:
        return Question(
            id=self.id,
            text=self.text,
            tags=self.tags,
            difficulty=self.difficulty,
            follow_up=self.follow_up,
        )


class SkillGap(BaseModel):
    skill: str
    required_level: SkillLevel
    resume_level: ResumeMatchLevel


class SkillsAnalysis(BaseModel):
    required_skills: list[str]
    skill_gaps: list[SkillGap]
    summary: str


class InterviewPlan(BaseModel):
    """Serialisable interview plan produced by the planner agent or hand-crafted.

    Load with ``InterviewPlan.from_yaml(path)`` and pass to the engine via
    ``interviewd interview --plan <path>``.
    """

    generated_at: str
    jd_source: str = ""
    resume_source: str = ""
    interview_type: InterviewType
    difficulty: DifficultyLevel
    num_questions: int
    time_limit_per_question: int = 120
    persona: PersonaType = "neutral"
    language: str = "en"
    skills_analysis: SkillsAnalysis
    questions: list[PlannedQuestion]

    @classmethod
    def from_yaml(cls, path: str) -> "InterviewPlan":
        import yaml
        from pathlib import Path

        with Path(path).open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def to_questions(self) -> list[Question]:
        return [q.to_question() for q in self.questions]
