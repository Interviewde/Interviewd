"""In-memory state for active (in-progress) web interview sessions.

Completed sessions are persisted to SessionStore (SQLite). This dict only
holds sessions that have not yet finished. If the server restarts mid-interview
the user simply starts a new session — acceptable for a local tool.
"""
from dataclasses import dataclass, field

from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.interview import Turn

_active: dict[str, "WebInterviewState"] = {}


@dataclass
class WebInterviewState:
    config: InterviewConfig
    questions: list[Question]
    current_index: int = 0
    turns: list[Turn] = field(default_factory=list)
    # When True the next audio submission is treated as the follow-up answer
    # for the turn at (current_index - 1).
    awaiting_follow_up: bool = False
    current_main_answer: str = ""


def create(session_id: str, state: WebInterviewState) -> None:
    _active[session_id] = state


def get(session_id: str) -> WebInterviewState | None:
    return _active.get(session_id)


def remove(session_id: str) -> None:
    _active.pop(session_id, None)
