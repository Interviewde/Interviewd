"""In-memory state for active practice sessions.

Practice sessions are lighter than full interview sessions — they hold one
question at a time with a full free-form conversation history, and are never
persisted to the session store (practice is not scored).
"""
from dataclasses import dataclass, field

from interviewd.data.question_bank import Question

_active: dict[str, "PracticeSessionState"] = {}


@dataclass
class PracticeSessionState:
    questions: list[Question]          # ordered list of questions selected to practice
    current_idx: int = 0
    # Conversation history for the *current* question only.
    # Each entry: {"role": "agent" | "user", "text": str}
    history: list[dict] = field(default_factory=list)


def create(session_id: str, state: PracticeSessionState) -> None:
    _active[session_id] = state


def get(session_id: str) -> PracticeSessionState | None:
    return _active.get(session_id)


def remove(session_id: str) -> None:
    _active.pop(session_id, None)
