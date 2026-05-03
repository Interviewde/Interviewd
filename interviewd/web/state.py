"""In-memory state for active (in-progress) web interview sessions.

Completed sessions are persisted to SessionStore (SQLite). This dict only
holds sessions that have not yet finished. If the server restarts mid-interview
the user simply starts a new session — acceptable for a local tool.
"""
from dataclasses import dataclass, field
from datetime import datetime

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

    # When the interview started — used to enforce config.total_time_limit.
    started_at: datetime | None = None

    # --- Follow-up tracking (all reset between questions) ---
    # True while waiting for the candidate to answer a follow-up question.
    awaiting_follow_up: bool = False
    # The main answer given before any follow-ups started.
    current_main_answer: str = ""
    # How many follow-up exchanges have been completed for the current question.
    follow_up_count: int = 0
    # Completed (question_text, answer) pairs for the current question.
    follow_up_history: list[tuple[str, str]] = field(default_factory=list)
    # The follow-up question whose answer we are currently waiting on.
    current_follow_up_question: str = ""

    # --- Clarification tracking (reset when a main answer is accepted) ---
    # How many clarification exchanges have occurred for the current question.
    clarification_count: int = 0
    # Completed (candidate_question, agent_answer) pairs for the current question.
    current_clarifications: list[tuple[str, str]] = field(default_factory=list)


def _reset_question_state(st: WebInterviewState) -> None:
    """Clear all per-question tracking fields after a turn is completed."""
    st.awaiting_follow_up = False
    st.current_main_answer = ""
    st.follow_up_count = 0
    st.follow_up_history.clear()
    st.current_follow_up_question = ""
    st.clarification_count = 0
    st.current_clarifications.clear()


def create(session_id: str, state: WebInterviewState) -> None:
    _active[session_id] = state


def get(session_id: str) -> WebInterviewState | None:
    return _active.get(session_id)


def remove(session_id: str) -> None:
    _active.pop(session_id, None)
