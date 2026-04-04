"""CLI integration tests.

The `interview` command is hardware-bound (mic + speakers), so we mock at
the adapter/engine/scorer boundary and verify the wiring: that the session
is persisted and the session ID is printed.

The `report` and `sessions` commands are pure DB reads and are tested against
a real (tmp) SessionStore.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from interviewd.cli.main import app
from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.interview import InterviewSession, Turn
from interviewd.scoring.scorer import AnswerScore, ScoreReport
from interviewd.store.session_store import SessionStore

runner = CliRunner()

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_CONFIG = InterviewConfig(
    type="behavioral", difficulty="mid", num_questions=1,
    time_limit_per_question=120, persona="neutral", language="en",
)

_QUESTION = Question(
    id="q1", text="Tell me about a challenge.",
    tags=[], difficulty="mid", follow_up="",
)

_SESSION = InterviewSession(
    config=_CONFIG,
    turns=[Turn(question=_QUESTION, answer="I solved a hard bug.")],
)

_REPORT = ScoreReport(
    scores=[
        AnswerScore(
            question_id="q1",
            question_text="Tell me about a challenge.",
            answer="I solved a hard bug.",
            star_score=7, relevance_score=8, clarity_score=6,
            feedback="Add more detail about the outcome.",
        )
    ],
    summary="Good answer overall.",
)


# ---------------------------------------------------------------------------
# interview command
# ---------------------------------------------------------------------------


def test_interview_saves_session_and_prints_id(tmp_path):
    """interview command runs the full pipeline, persists, and prints session ID.

    We mock the adapters and engine/scorer so no hardware is needed.
    asyncio.run is NOT mocked — the real event loop executes the coroutine.
    """
    with (
        patch("interviewd.adapters.vad.registry.get_vad_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.stt.registry.get_stt_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.tts.registry.get_tts_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.llm.registry.get_llm_adapter", return_value=MagicMock()),
        patch("interviewd.data.question_bank.QuestionBank.pick", return_value=[_QUESTION]),
        patch("interviewd.engine.interview.InterviewEngine.run", new=AsyncMock(return_value=_SESSION)),
        patch("interviewd.scoring.scorer.Scorer.score", new=AsyncMock(return_value=_REPORT)),
        patch("interviewd.config.load_settings") as mock_load_settings,
    ):
        settings = MagicMock()
        settings.interview.time_limit_per_question = 120
        settings.interview.persona = "neutral"
        settings.interview.language = "en"
        settings.paths.question_bank = "config/questions"
        settings.paths.session_store = str(tmp_path / "sessions")
        mock_load_settings.return_value = settings

        result = runner.invoke(app, ["interview", "--questions", "1"])

    assert result.exit_code == 0, result.output
    assert "Session saved" in result.output
    assert "Overall score" in result.output


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_store(tmp_path):
    store = SessionStore(store_dir=str(tmp_path / "sessions"))
    session_id = store.save(_SESSION, _REPORT)
    return store, session_id, str(tmp_path / "sessions")


def test_report_prints_transcript_and_scores(populated_store, tmp_path):
    _store, session_id, store_dir = populated_store

    with patch("interviewd.config.load_settings") as mock_settings:
        s = MagicMock()
        s.paths.session_store = store_dir
        mock_settings.return_value = s

        result = runner.invoke(app, ["report", session_id])

    assert result.exit_code == 0, result.output
    assert "behavioral" in result.output
    assert "Tell me about a challenge." in result.output
    assert "I solved a hard bug." in result.output
    assert "Add more detail about the outcome." in result.output
    assert "Good answer overall." in result.output
    assert "SUMMARY" in result.output


def test_report_unknown_id_exits_with_error(tmp_path):
    with patch("interviewd.config.load_settings") as mock_settings:
        s = MagicMock()
        s.paths.session_store = str(tmp_path / "sessions")
        mock_settings.return_value = s

        result = runner.invoke(app, ["report", "00000000-0000-0000-0000-000000000000"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower() or "not found" in (result.stderr or "").lower()


# ---------------------------------------------------------------------------
# sessions command
# ---------------------------------------------------------------------------


def test_sessions_empty(tmp_path):
    with patch("interviewd.config.load_settings") as mock_settings:
        s = MagicMock()
        s.paths.session_store = str(tmp_path / "sessions")
        mock_settings.return_value = s

        result = runner.invoke(app, ["sessions"])

    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_sessions_lists_saved(populated_store):
    _store, session_id, store_dir = populated_store

    with patch("interviewd.config.load_settings") as mock_settings:
        s = MagicMock()
        s.paths.session_store = store_dir
        mock_settings.return_value = s

        result = runner.invoke(app, ["sessions"])

    assert result.exit_code == 0, result.output
    assert session_id in result.output
    assert "behavioral" in result.output
    assert "mid" in result.output
