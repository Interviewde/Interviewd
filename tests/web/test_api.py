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


def _mock_llm(response: str = "SATISFIED") -> MagicMock:
    """Default response of SATISFIED means: not a clarification, no follow-up needed."""
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=response)
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
        c.app.state.stt = _mock_stt()
        c.app.state.tts = _mock_tts()
        c.app.state.llm = _mock_llm()   # "SATISFIED" → no follow-up, no clarification
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


def test_answer_follow_up_when_probe_not_satisfied(client, tmp_path):
    """When LLM returns a follow-up question (not SATISFIED/SKIP), status should be follow_up."""
    from interviewd.store.session_store import SessionStore
    from interviewd.web.app import app

    with TestClient(app) as c:
        c.app.state.stt = _mock_stt()
        c.app.state.tts = _mock_tts()
        # "Can you elaborate?" → not CLARIFICATION, not SATISFIED, not SKIP → follow_up
        c.app.state.llm = _mock_llm("Can you elaborate?")
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "fu_sessions"))

        sid = c.post(
            "/api/interview/start",
            json={"type": "behavioral", "difficulty": "mid", "num_questions": 1},
        ).json()["session_id"]

        res = c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )
        body = res.json()
        assert body["status"] == "follow_up"
        assert body["question"]["is_follow_up"] is True
        assert body["question"]["text"] == "Can you elaborate?"


def test_answer_skip_returns_skip_message(client, tmp_path):
    """When LLM returns SKIP, response includes skip_message and advances."""
    from interviewd.engine.interview import SKIP_MESSAGE
    from interviewd.store.session_store import SessionStore
    from interviewd.web.app import app

    with TestClient(app) as c:
        c.app.state.stt = _mock_stt()
        c.app.state.tts = _mock_tts()
        c.app.state.llm = _mock_llm("SKIP")
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "skip_sessions"))

        sid = c.post(
            "/api/interview/start",
            json={"type": "behavioral", "difficulty": "mid", "num_questions": 2},
        ).json()["session_id"]

        res = c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )
        body = res.json()
        # Should still advance (next_question for a 2-question session)
        assert body["status"] == "next_question"
        assert body["skip_message"] == SKIP_MESSAGE


def test_completing_all_questions_saves_session(client):
    """Answering all questions (no follow-up) ends with status=complete and a persisted session."""
    sid = _start(client, num_questions=1)
    res = _submit(client, sid)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "complete"
    assert body["end_reason"] == "completed"
    saved_id = body["session_id"]
    assert saved_id
    # UI session ID must equal stored ID
    assert saved_id == sid

    get_res = client.get(f"/api/sessions/{saved_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["session"]["config"]["type"] == "behavioral"
    assert data["session"]["completion_status"] == "completed"
    assert data["report"]["summary"] == "Solid performance."


# ---------------------------------------------------------------------------
# Voice-end intent
# ---------------------------------------------------------------------------


def test_voice_end_intent_finalizes_session(tmp_path):
    """Saying 'I want to end the interview' should save with completion_status='ended_by_voice'."""
    from interviewd.engine.interview import END_INTENT_MESSAGE
    from interviewd.store.session_store import SessionStore
    from interviewd.web.app import app

    with TestClient(app) as c:
        c.app.state.stt = _mock_stt("I'd like to end the interview now please.")
        c.app.state.tts = _mock_tts()
        # detect_end_intent will see the keyword, call LLM → "END"
        c.app.state.llm = _mock_llm("END")
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "voice_end_sessions"))

        sid = c.post(
            "/api/interview/start",
            json={"type": "behavioral", "difficulty": "mid", "num_questions": 5},
        ).json()["session_id"]

        # Answer one question normally first so we have something to score.
        c.app.state.stt = _mock_stt("My answer.")
        c.app.state.llm = _mock_llm("SATISFIED")
        c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )

        # Now say end-intent.
        c.app.state.stt = _mock_stt("Can we please end the interview now?")
        c.app.state.llm = _mock_llm("END")
        res = c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )
        body = res.json()
        assert body["status"] == "complete"
        assert body["end_reason"] == "ended_by_voice"
        assert body["end_message"] == END_INTENT_MESSAGE

        get_res = c.get(f"/api/sessions/{sid}")
        assert get_res.json()["session"]["completion_status"] == "ended_by_voice"


# ---------------------------------------------------------------------------
# Time limit
# ---------------------------------------------------------------------------


def test_time_limit_finalizes_session(tmp_path):
    """When elapsed time exceeds total_time_limit, save with completion_status='timed_out'."""
    from datetime import datetime, timedelta, timezone

    from interviewd.store.session_store import SessionStore
    from interviewd.web import state as session_state
    from interviewd.web.app import app

    with TestClient(app) as c:
        c.app.state.stt = _mock_stt("My answer.")
        c.app.state.tts = _mock_tts()
        c.app.state.llm = _mock_llm("SATISFIED")
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "timed_sessions"))

        sid = c.post(
            "/api/interview/start",
            json={
                "type": "behavioral",
                "difficulty": "mid",
                "num_questions": 5,
                "total_time_limit": 60,
            },
        ).json()["session_id"]

        # First answer normally — gives us at least one turn to score.
        c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )

        # Force the start time into the past so the next answer trips the limit.
        st = session_state.get(sid)
        st.started_at = datetime.now(timezone.utc) - timedelta(seconds=120)

        res = c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )
        body = res.json()
        assert body["status"] == "complete"
        assert body["end_reason"] == "timed_out"

        get_res = c.get(f"/api/sessions/{sid}")
        assert get_res.json()["session"]["completion_status"] == "timed_out"


# ---------------------------------------------------------------------------
# End interview button
# ---------------------------------------------------------------------------


def test_end_interview_button_marks_ended_early(client):
    sid = _start(client, num_questions=5)
    # Answer one question so there's something to score.
    _submit(client, sid)
    res = client.post(f"/api/interview/{sid}/end")
    assert res.status_code == 200
    saved_id = res.json()["session_id"]
    assert saved_id == sid  # UI ID matches stored ID

    data = client.get(f"/api/sessions/{saved_id}").json()
    assert data["session"]["completion_status"] == "ended_early"


def test_end_interview_with_no_turns_returns_null(client):
    sid = _start(client, num_questions=2)
    res = client.post(f"/api/interview/{sid}/end")
    assert res.json()["session_id"] is None


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


# ---------------------------------------------------------------------------
# Clarification flow
# ---------------------------------------------------------------------------


def test_clarification_then_answer_completes(tmp_path):
    """Clarification request → clarification response → actual answer → complete."""
    from interviewd.store.session_store import SessionStore
    from interviewd.web.app import app

    # LLM response sequence:
    # 1. detect_clarification("what do you mean?") → "CLARIFICATION"
    # 2. generate_clarification(...)               → "Here is more context."
    # 3. detect_clarification("My real answer.")   → "ANSWER"
    # 4. probe_answer("My real answer.")            → "SATISFIED"
    responses = iter(["CLARIFICATION", "Here is more context.", "ANSWER", "SATISFIED"])

    async def _llm_side_effect(messages, stream=True):
        return next(responses)

    llm = MagicMock()
    llm.complete = _llm_side_effect

    with TestClient(app) as c:
        c.app.state.stt = _mock_stt("My real answer.")
        c.app.state.tts = _mock_tts()
        c.app.state.llm = llm
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "clarif_sessions"))

        sid = c.post(
            "/api/interview/start",
            json={"type": "behavioral", "difficulty": "mid", "num_questions": 1},
        ).json()["session_id"]

        # First submission — asking for clarification
        res1 = c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )
        assert res1.status_code == 200, res1.text
        body1 = res1.json()
        assert body1["status"] == "clarification"
        assert body1["clarification_text"] == "Here is more context."
        assert body1["question"]["index"] == 0

        # Second submission — actual answer after clarification
        res2 = c.post(
            f"/api/interview/{sid}/answer",
            files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")},
        )
        assert res2.status_code == 200, res2.text
        body2 = res2.json()
        assert body2["status"] == "complete"
        assert body2["session_id"]


def test_clarification_preserves_clarification_in_saved_turn(tmp_path):
    """Clarifications are stored in the Turn and persisted to the session store."""
    from interviewd.store.session_store import SessionStore
    from interviewd.web.app import app

    responses = iter(["CLARIFICATION", "More context here.", "ANSWER", "SATISFIED"])

    async def _llm(messages, stream=True):
        return next(responses)

    llm = MagicMock()
    llm.complete = _llm

    with TestClient(app) as c:
        c.app.state.stt = _mock_stt("My real answer.")
        c.app.state.tts = _mock_tts()
        c.app.state.llm = llm
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "clarif_persist"))

        sid = c.post(
            "/api/interview/start",
            json={"type": "behavioral", "difficulty": "mid", "num_questions": 1},
        ).json()["session_id"]

        c.post(f"/api/interview/{sid}/answer",
               files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")})
        complete = c.post(f"/api/interview/{sid}/answer",
                          files={"audio": ("audio.webm", _FAKE_AUDIO, "audio/webm")}).json()

        saved_id = complete["session_id"]
        data = c.get(f"/api/sessions/{saved_id}").json()
        turn = data["session"]["turns"][0]
        assert len(turn["clarifications"]) == 1
        assert turn["clarifications"][0]["agent"] == "More context here."
