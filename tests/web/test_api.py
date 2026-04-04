"""Tests for the FastAPI web layer.

Strategy: use FastAPI's TestClient (sync), override app.state with mocks
immediately after the lifespan runs, so ensure_adapters() sees non-None
adapters and skips real initialisation. No API keys needed.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from interviewd.data.question_bank import Question
from interviewd.engine.interview import InterviewSession, Turn
from interviewd.scoring.scorer import AnswerScore, ScoreReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FAKE_AUDIO = b"\x00" * 64  # minimal non-empty bytes


def _mock_stt(transcript: str = "My test answer.") -> MagicMock:
    stt = MagicMock()
    stt.transcribe = AsyncMock(return_value=transcript)
    return stt


def _mock_tts(audio: bytes = b"\xff\xfb\x90") -> MagicMock:
    tts = MagicMock()
    tts.synthesize = AsyncMock(return_value=audio)
    return tts


def _mock_llm(follow_up: str = "NO") -> MagicMock:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=follow_up)
    return llm


def _mock_scorer() -> MagicMock:
    scorer = MagicMock()
    report = ScoreReport(
        scores=[
            AnswerScore(
                question_id="b001",
                question_text="Tell me about a time you had to deal with a difficult team member.",
                answer="My test answer.",
                star_score=7,
                relevance_score=8,
                clarity_score=6,
                feedback="Good structure.",
            )
        ],
        summary="Solid performance.",
    )
    scorer.score = AsyncMock(return_value=report)
    return scorer


@pytest.fixture
def client(tmp_path):
    """TestClient with all adapters mocked and a real SessionStore in tmp_path."""
    from interviewd.store.session_store import SessionStore
    from interviewd.web.app import app

    with TestClient(app) as c:
        # lifespan sets these to None; override before any request is made.
        # ensure_adapters() checks `if app_state.llm is not None: return`
        # so setting llm (and the others) prevents real initialisation.
        c.app.state.stt = _mock_stt()
        c.app.state.tts = _mock_tts()
        c.app.state.llm = _mock_llm()
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "sessions"))
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Interview — start
# ---------------------------------------------------------------------------


def test_start_interview_returns_first_question(client):
    res = client.post(
        "/api/interview/start",
        json={"type": "behavioral", "difficulty": "mid", "num_questions": 2},
    )
    assert res.status_code == 200
    body = res.json()
    assert "session_id" in body
    assert body["question"]["index"] == 0
    assert body["question"]["total"] == 2
    assert body["question"]["is_follow_up"] is False
    assert body["question"]["text"]  # non-empty


def test_start_interview_invalid_type(client):
    res = client.post(
        "/api/interview/start",
        json={"type": "gibberish", "difficulty": "mid", "num_questions": 1},
    )
    assert res.status_code == 400


def test_start_interview_invalid_difficulty(client):
    res = client.post(
        "/api/interview/start",
        json={"type": "behavioral", "difficulty": "expert", "num_questions": 1},
    )
    assert res.status_code == 400


def test_start_interview_no_questions_available(client):
    # system_design has no entry-level questions
    res = client.post(
        "/api/interview/start",
        json={"type": "system_design", "difficulty": "entry", "num_questions": 5},
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Interview — answer submission
# ---------------------------------------------------------------------------


def _start(client, *, interview_type="behavioral", difficulty="mid", num_questions=2):
    """Helper: start an interview and return its session_id."""
    res = client.post(
        "/api/interview/start",
        json={"type": interview_type, "difficulty": difficulty, "num_questions": num_questions},
    )
    assert res.status_code == 200
    return res.json()["session_id"]


def _submit(client, session_id, audio=_FAKE_AUDIO):
    return client.post(
        f"/api/interview/{session_id}/answer",
        files={"audio": ("audio.webm", audio, "audio/webm")},
    )


def test_answer_advances_to_next_question(client):
    sid = _start(client, num_questions=2)
    res = _submit(client, sid)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "next_question"
    assert body["question"]["index"] == 1
    assert body["transcript"] == "My test answer."


def test_answer_unknown_session_returns_404(client):
    res = _submit(client, "00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_answer_follow_up_when_llm_says_yes(client, tmp_path):
    """When LLM returns YES the next response should be a follow_up."""
    from interviewd.store.session_store import SessionStore
    from interviewd.web.app import app

    with TestClient(app) as c:
        c.app.state.stt = _mock_stt()
        c.app.state.tts = _mock_tts()
        c.app.state.llm = _mock_llm(follow_up="YES")
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "fu_sessions"))

        sid_res = c.post(
            "/api/interview/start",
            json={"type": "behavioral", "difficulty": "mid", "num_questions": 1},
        )
        sid = sid_res.json()["session_id"]

        res = c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )
        body = res.json()
        assert body["status"] == "follow_up"
        assert body["question"]["is_follow_up"] is True


def test_completing_all_questions_saves_session(client):
    """Answering all questions (no follow-up) ends with status=complete and a persisted session."""
    sid = _start(client, num_questions=1)
    res = _submit(client, sid)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "complete"
    saved_id = body["session_id"]
    assert saved_id  # non-empty UUID

    # Session must be retrievable from the store
    get_res = client.get(f"/api/sessions/{saved_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["session"]["config"]["type"] == "behavioral"
    assert data["report"]["summary"] == "Solid performance."


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


def test_tts_returns_audio_bytes(client):
    res = client.get("/api/interview/tts?text=Hello+world")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("audio/")
    assert len(res.content) > 0


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def test_list_sessions_empty(client):
    res = client.get("/api/sessions")
    assert res.status_code == 200
    assert res.json() == []


def test_list_sessions_returns_saved(client):
    # Complete one interview first
    sid = _start(client, num_questions=1)
    _submit(client, sid)

    res = client.get("/api/sessions")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["interview_type"] == "behavioral"
    assert rows[0]["avg_overall"] is not None


def test_get_session_not_found(client):
    res = client.get("/api/sessions/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_get_session_full_report(client):
    sid = _start(client, num_questions=1)
    complete = _submit(client, sid).json()
    saved_id = complete["session_id"]

    res = client.get(f"/api/sessions/{saved_id}")
    assert res.status_code == 200
    data = res.json()

    assert len(data["session"]["turns"]) == 1
    assert len(data["report"]["scores"]) == 1
    assert data["report"]["scores"][0]["star_score"] == 7
    assert data["report"]["scores"][0]["feedback"] == "Good structure."
    assert data["report"]["summary"] == "Solid performance."
