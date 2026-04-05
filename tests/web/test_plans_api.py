"""Tests for the plans API endpoints:
  GET  /api/plans           — list standard plans
  POST /api/plans/generate  — run planner agent, return plan JSON
  POST /api/interview/start — with plan_id or plan_data
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from interviewd.planner.models import InterviewPlan, PlannedQuestion, SkillGap, SkillsAnalysis
from interviewd.scoring.scorer import AnswerScore, ScoreReport


# ---------------------------------------------------------------------------
# Shared mock helpers (mirrors test_api.py)
# ---------------------------------------------------------------------------


def _mock_stt(transcript: str = "My answer.") -> MagicMock:
    m = MagicMock()
    m.transcribe = AsyncMock(return_value=transcript)
    return m


def _mock_tts() -> MagicMock:
    m = MagicMock()
    m.synthesize = AsyncMock(return_value=b"\xff\xfb\x90")
    return m


def _mock_llm(response: str = "NO") -> MagicMock:
    m = MagicMock()
    m.complete = AsyncMock(return_value=response)
    return m


def _mock_scorer() -> MagicMock:
    m = MagicMock()
    report = ScoreReport(
        scores=[
            AnswerScore(
                question_id="plan_001",
                question_text="Q?",
                answer="My answer.",
                star_score=7,
                relevance_score=8,
                clarity_score=6,
                feedback="Good.",
            )
        ],
        summary="Solid.",
    )
    m.score = AsyncMock(return_value=report)
    return m


def _make_plan() -> InterviewPlan:
    return InterviewPlan(
        generated_at="2026-04-05T00:00:00+00:00",
        interview_type="technical",
        difficulty="senior",
        num_questions=1,
        skills_analysis=SkillsAnalysis(
            required_skills=["Python"],
            skill_gaps=[SkillGap(skill="Kubernetes", required_level="high", resume_level="missing")],
            summary="Strong Python; no K8s.",
        ),
        questions=[
            PlannedQuestion(
                id="plan_001",
                text="Describe your Kubernetes experience.",
                tags=["kubernetes"],
                difficulty="senior",
                follow_up="",
                rationale="K8s gap.",
            )
        ],
    )


@pytest.fixture
def client(tmp_path):
    from interviewd.store.session_store import SessionStore
    from interviewd.web.app import app

    with TestClient(app) as c:
        c.app.state.stt = _mock_stt()
        c.app.state.tts = _mock_tts()
        c.app.state.llm = _mock_llm()
        c.app.state.scorer = _mock_scorer()
        c.app.state.store = SessionStore(str(tmp_path / "sessions"))
        yield c


# ---------------------------------------------------------------------------
# GET /api/plans
# ---------------------------------------------------------------------------


def test_list_plans_returns_list(client):
    res = client.get("/api/plans")
    assert res.status_code == 200
    plans = res.json()
    assert isinstance(plans, list)


def test_list_plans_includes_standard_plans(client):
    res = client.get("/api/plans")
    ids = [p["id"] for p in res.json()]
    assert "swe_technical_senior" in ids
    assert "pm_behavioral_mid" in ids


def test_list_plans_has_required_fields(client):
    res = client.get("/api/plans")
    plan = next(p for p in res.json() if p["id"] == "swe_technical_senior")
    assert plan["title"]
    assert plan["interview_type"] == "technical"
    assert plan["difficulty"] == "senior"
    assert plan["num_questions"] == 5
    assert plan["summary"]


def test_list_plans_empty_dir(client, tmp_path, monkeypatch):
    """Returns empty list when config/plans/ is missing or empty."""
    import interviewd.web.api.plans as plans_module
    monkeypatch.setattr(plans_module, "_PLANS_DIR", tmp_path / "nonexistent")
    res = client.get("/api/plans")
    assert res.status_code == 200
    assert res.json() == []


# ---------------------------------------------------------------------------
# POST /api/plans/generate
# ---------------------------------------------------------------------------


def _generate_body(tmp_path, interview_type="technical", difficulty="senior", num_questions=2):
    jd = tmp_path / "jd.txt"
    resume = tmp_path / "resume.txt"
    jd.write_text("We need a Python/Kubernetes engineer.", encoding="utf-8")
    resume.write_text("5 years Python. No cloud.", encoding="utf-8")
    return jd, resume, interview_type, difficulty, num_questions


def test_generate_plan_returns_valid_plan(client, tmp_path):
    fake_plan = _make_plan()

    with patch("interviewd.planner.agent.PlannerAgent") as MockAgent:
        MockAgent.return_value.run = AsyncMock(return_value=fake_plan)

        jd, resume, t, d, n = _generate_body(tmp_path)
        res = client.post(
            "/api/plans/generate",
            data={"interview_type": t, "difficulty": d, "num_questions": n},
            files={
                "jd_file": ("jd.txt", jd.read_bytes(), "text/plain"),
                "resume_file": ("resume.txt", resume.read_bytes(), "text/plain"),
            },
        )

    assert res.status_code == 200
    body = res.json()
    assert body["interview_type"] == "technical"
    assert body["difficulty"] == "senior"
    assert len(body["questions"]) == 1
    assert body["skills_analysis"]["skill_gaps"][0]["skill"] == "Kubernetes"


def test_generate_plan_invalid_type(client, tmp_path):
    jd, resume, _, d, n = _generate_body(tmp_path)
    res = client.post(
        "/api/plans/generate",
        data={"interview_type": "sales", "difficulty": d, "num_questions": n},
        files={
            "jd_file": ("jd.txt", jd.read_bytes(), "text/plain"),
            "resume_file": ("resume.txt", resume.read_bytes(), "text/plain"),
        },
    )
    assert res.status_code == 400


def test_generate_plan_invalid_difficulty(client, tmp_path):
    jd, resume, t, _, n = _generate_body(tmp_path)
    res = client.post(
        "/api/plans/generate",
        data={"interview_type": t, "difficulty": "wizard", "num_questions": n},
        files={
            "jd_file": ("jd.txt", jd.read_bytes(), "text/plain"),
            "resume_file": ("resume.txt", resume.read_bytes(), "text/plain"),
        },
    )
    assert res.status_code == 400


def test_generate_plan_num_questions_out_of_range(client, tmp_path):
    jd, resume, t, d, _ = _generate_body(tmp_path)
    res = client.post(
        "/api/plans/generate",
        data={"interview_type": t, "difficulty": d, "num_questions": 0},
        files={
            "jd_file": ("jd.txt", jd.read_bytes(), "text/plain"),
            "resume_file": ("resume.txt", resume.read_bytes(), "text/plain"),
        },
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/interview/start — with plan_id
# ---------------------------------------------------------------------------


def test_start_with_plan_id_uses_plan_questions(client):
    res = client.post(
        "/api/interview/start",
        json={"type": "behavioral", "difficulty": "mid", "num_questions": 5,
              "persona": "neutral", "plan_id": "swe_technical_senior"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "session_id" in body
    # swe_technical_senior has 5 questions
    assert body["question"]["total"] == 5


def test_start_with_unknown_plan_id_returns_404(client):
    res = client.post(
        "/api/interview/start",
        json={"type": "behavioral", "difficulty": "mid", "num_questions": 5,
              "persona": "neutral", "plan_id": "nonexistent_plan"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/interview/start — with plan_data
# ---------------------------------------------------------------------------


def test_start_with_plan_data_uses_plan_questions(client):
    plan = _make_plan()
    res = client.post(
        "/api/interview/start",
        json={
            "type": "behavioral",
            "difficulty": "mid",
            "num_questions": 5,
            "persona": "neutral",
            "plan_data": plan.model_dump(),
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["question"]["total"] == 1  # plan has 1 question
    assert body["question"]["text"] == "Describe your Kubernetes experience."


def test_start_with_malformed_plan_data_returns_400(client):
    res = client.post(
        "/api/interview/start",
        json={
            "type": "behavioral",
            "difficulty": "mid",
            "num_questions": 5,
            "persona": "neutral",
            "plan_data": {"not": "a valid plan"},
        },
    )
    assert res.status_code == 400
