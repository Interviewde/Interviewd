import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.interview import InterviewSession, Turn
from interviewd.scoring.scorer import AnswerScore, ScoreReport

_DDL = """
CREATE TABLE IF NOT EXISTS interview_sessions (
    id                      TEXT PRIMARY KEY,
    created_at              TEXT NOT NULL,
    interview_type          TEXT NOT NULL,
    difficulty              TEXT NOT NULL,
    num_questions           INTEGER NOT NULL,
    time_limit_per_question INTEGER NOT NULL,
    persona                 TEXT NOT NULL,
    language                TEXT NOT NULL,
    score_summary           TEXT,
    avg_overall             REAL
);

CREATE TABLE IF NOT EXISTS turns (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL REFERENCES interview_sessions(id),
    position            INTEGER NOT NULL,
    question_id         TEXT NOT NULL,
    question_text       TEXT NOT NULL,
    question_tags       TEXT NOT NULL DEFAULT '[]',
    question_difficulty TEXT NOT NULL,
    question_follow_up  TEXT NOT NULL DEFAULT '',
    answer              TEXT NOT NULL,
    follow_up_asked     INTEGER NOT NULL DEFAULT 0,
    follow_up_answer    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS answer_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES interview_sessions(id),
    question_id     TEXT NOT NULL,
    question_text   TEXT NOT NULL,
    answer          TEXT NOT NULL,
    star_score      INTEGER NOT NULL,
    relevance_score INTEGER NOT NULL,
    clarity_score   INTEGER NOT NULL,
    feedback        TEXT NOT NULL
);
"""


class SavedSession(NamedTuple):
    session_id: str
    interview_session: InterviewSession
    score_report: ScoreReport


class SessionStore:
    """SQLite-backed store for interview sessions and score reports.

    The database lives at ``{store_dir}/interviews.db``.
    The directory is created automatically on first use.

    Usage::

        store = SessionStore(".interviewd/sessions")
        session_id = store.save(session, report)
        saved = store.load(session_id)
        rows = store.list_sessions()
    """

    def __init__(self, store_dir: str = ".interviewd/sessions") -> None:
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db_path = str(self._dir / "interviews.db")
        with self._connect() as con:
            con.executescript(_DDL)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, session: InterviewSession, report: ScoreReport) -> str:
        """Persist a session and its score report.  Returns the session ID."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as con:
            con.execute(
                """INSERT INTO interview_sessions
                   (id, created_at, interview_type, difficulty, num_questions,
                    time_limit_per_question, persona, language,
                    score_summary, avg_overall)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id, now,
                    session.config.type, session.config.difficulty,
                    session.config.num_questions,
                    session.config.time_limit_per_question,
                    session.config.persona, session.config.language,
                    report.summary, report.average_overall,
                ),
            )

            con.executemany(
                """INSERT INTO turns
                   (session_id, position, question_id, question_text,
                    question_tags, question_difficulty, question_follow_up,
                    answer, follow_up_asked, follow_up_answer)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                [
                    (
                        session_id, pos,
                        t.question.id, t.question.text,
                        json.dumps(t.question.tags),
                        t.question.difficulty, t.question.follow_up,
                        t.answer, int(t.follow_up_asked), t.follow_up_answer,
                    )
                    for pos, t in enumerate(session.turns)
                ],
            )

            con.executemany(
                """INSERT INTO answer_scores
                   (session_id, question_id, question_text, answer,
                    star_score, relevance_score, clarity_score, feedback)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [
                    (
                        session_id,
                        s.question_id, s.question_text, s.answer,
                        s.star_score, s.relevance_score, s.clarity_score,
                        s.feedback,
                    )
                    for s in report.scores
                ],
            )

        return session_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(self, session_id: str) -> SavedSession:
        """Load a session by ID.

        Raises:
            KeyError: If no session with the given ID exists.
        """
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM interview_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Session not found: {session_id}")

            config = InterviewConfig(
                type=row["interview_type"],
                difficulty=row["difficulty"],
                num_questions=row["num_questions"],
                time_limit_per_question=row["time_limit_per_question"],
                persona=row["persona"],
                language=row["language"],
            )

            turn_rows = con.execute(
                "SELECT * FROM turns WHERE session_id = ? ORDER BY position",
                (session_id,),
            ).fetchall()
            turns = [
                Turn(
                    question=Question(
                        id=t["question_id"],
                        text=t["question_text"],
                        tags=json.loads(t["question_tags"]),
                        difficulty=t["question_difficulty"],
                        follow_up=t["question_follow_up"],
                    ),
                    answer=t["answer"],
                    follow_up_asked=bool(t["follow_up_asked"]),
                    follow_up_answer=t["follow_up_answer"],
                )
                for t in turn_rows
            ]

            score_rows = con.execute(
                "SELECT * FROM answer_scores WHERE session_id = ?", (session_id,)
            ).fetchall()
            scores = [
                AnswerScore(
                    question_id=s["question_id"],
                    question_text=s["question_text"],
                    answer=s["answer"],
                    star_score=s["star_score"],
                    relevance_score=s["relevance_score"],
                    clarity_score=s["clarity_score"],
                    feedback=s["feedback"],
                )
                for s in score_rows
            ]

        return SavedSession(
            session_id=session_id,
            interview_session=InterviewSession(config=config, turns=turns),
            score_report=ScoreReport(scores=scores, summary=row["score_summary"] or ""),
        )

    def list_sessions(self) -> list[dict]:
        """Return a summary of all sessions, newest first.

        Each dict contains: ``id``, ``created_at``, ``interview_type``,
        ``difficulty``, ``avg_overall``.
        """
        with self._connect() as con:
            rows = con.execute(
                """SELECT id, created_at, interview_type, difficulty, avg_overall
                   FROM interview_sessions
                   ORDER BY created_at DESC, rowid DESC"""
            ).fetchall()
        return [dict(r) for r in rows]
