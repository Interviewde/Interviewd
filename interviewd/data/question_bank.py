import random
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from interviewd.config import InterviewConfig

DifficultyLevel = Literal["entry", "mid", "senior", "staff"]

# Numeric rank so we can include easier questions when filtering by difficulty.
_DIFFICULTY_RANK: dict[str, int] = {"entry": 0, "mid": 1, "senior": 2, "staff": 3}


class Question(BaseModel):
    id: str
    text: str
    tags: list[str] = []
    difficulty: DifficultyLevel
    follow_up: str = ""


class QuestionBank:
    """Loads questions from YAML files and filters by type and difficulty.

    YAML files live at ``{bank_dir}/{interview_type}.yaml`` and contain a
    top-level ``questions`` list.  Only questions whose difficulty rank is
    *at most* the requested level are eligible, so an "entry" session never
    receives "senior" questions.

    Usage::

        bank = QuestionBank("config/questions")
        questions = bank.pick(config)   # returns list[Question]
    """

    def __init__(self, bank_dir: str = "config/questions"):
        self._bank_dir = Path(bank_dir)

    def _load(self, interview_type: str) -> list[Question]:
        path = self._bank_dir / f"{interview_type}.yaml"
        if not path.exists():
            raise FileNotFoundError(
                f"No question bank for interview type '{interview_type}'. "
                f"Expected file: {path}"
            )
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return [Question.model_validate(q) for q in data.get("questions", [])]

    def pick(self, config: InterviewConfig, *, seed: int | None = None) -> list[Question]:
        """Return a randomised list of questions matching config.

        Args:
            config: Interview configuration supplying type, difficulty, and
                num_questions.
            seed: Optional RNG seed for reproducible picks (useful in tests).

        Returns:
            List of ``Question`` objects, length <= config.num_questions.
            If the bank has fewer eligible questions than requested, all
            eligible questions are returned (no error).
        """
        all_questions = self._load(config.type)
        max_rank = _DIFFICULTY_RANK[config.difficulty]
        eligible = [
            q for q in all_questions
            if _DIFFICULTY_RANK[q.difficulty] <= max_rank
        ]
        rng = random.Random(seed)
        return rng.sample(eligible, min(config.num_questions, len(eligible)))

    def available_types(self) -> list[str]:
        """Return interview types that have a YAML file in the bank directory."""
        return [p.stem for p in sorted(self._bank_dir.glob("*.yaml"))]
