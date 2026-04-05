"""Tests for the `interviewd plan` CLI command and `interview --plan` flag."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from interviewd.cli.main import app
from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.interview import InterviewSession, Turn
from interviewd.planner.models import InterviewPlan, PlannedQuestion, SkillGap, SkillsAnalysis
from interviewd.scoring.scorer import AnswerScore, ScoreReport

runner = CliRunner()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_plan(tmp_path: Path, num_questions: int = 2) -> InterviewPlan:
    return InterviewPlan(
        generated_at="2026-04-05T00:00:00+00:00",
        jd_source="job.txt",
        resume_source="resume.txt",
        interview_type="technical",
        difficulty="senior",
        num_questions=num_questions,
        skills_analysis=SkillsAnalysis(
            required_skills=["Python"],
            skill_gaps=[SkillGap(skill="Kubernetes", required_level="high", resume_level="missing")],
            summary="Strong Python; Kubernetes gap.",
        ),
        questions=[
            PlannedQuestion(
                id=f"plan_{i:03d}",
                text=f"Question {i}?",
                tags=["python"],
                difficulty="senior",
                follow_up="",
                rationale="reason",
            )
            for i in range(1, num_questions + 1)
        ],
    )


def _write_plan_yaml(tmp_path: Path, plan: InterviewPlan) -> Path:
    path = tmp_path / "plan.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(plan.model_dump(), f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


def _mock_settings(tmp_path: Path) -> MagicMock:
    s = MagicMock()
    s.interview.time_limit_per_question = 120
    s.interview.persona = "neutral"
    s.interview.language = "en"
    s.paths.question_bank = "config/questions"
    s.paths.session_store = str(tmp_path / "sessions")
    return s


# ---------------------------------------------------------------------------
# `interviewd plan` — success path
# ---------------------------------------------------------------------------


def test_plan_command_generates_and_saves_yaml(tmp_path):
    jd = tmp_path / "jd.txt"
    resume = tmp_path / "resume.txt"
    jd.write_text("Senior Python/K8s engineer needed.", encoding="utf-8")
    resume.write_text("5 years Python. No cloud.", encoding="utf-8")
    output = tmp_path / "out" / "plan.yaml"

    fake_plan = _make_plan(tmp_path)

    with (
        patch("interviewd.adapters.llm.registry.get_llm_adapter", return_value=MagicMock()),
        patch("interviewd.planner.agent.PlannerAgent.run", new=AsyncMock(return_value=fake_plan)),
        patch("interviewd.config.load_settings") as mock_load,
    ):
        s = MagicMock()
        mock_load.return_value = s

        result = runner.invoke(app, [
            "plan",
            "--jd", str(jd),
            "--resume", str(resume),
            "--output", str(output),
            "--type", "technical",
            "--difficulty", "senior",
            "--questions", "2",
        ])

    assert result.exit_code == 0, result.output
    assert "Plan saved" in result.output
    assert output.exists()

    with output.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data["interview_type"] == "technical"
    assert data["difficulty"] == "senior"
    assert len(data["questions"]) == 2


def test_plan_command_prints_focus_areas(tmp_path):
    jd = tmp_path / "jd.txt"
    resume = tmp_path / "resume.txt"
    jd.write_text("K8s required.", encoding="utf-8")
    resume.write_text("No K8s.", encoding="utf-8")

    fake_plan = _make_plan(tmp_path)

    with (
        patch("interviewd.adapters.llm.registry.get_llm_adapter", return_value=MagicMock()),
        patch("interviewd.planner.agent.PlannerAgent.run", new=AsyncMock(return_value=fake_plan)),
        patch("interviewd.config.load_settings", return_value=MagicMock()),
    ):
        result = runner.invoke(app, [
            "plan", "--jd", str(jd), "--resume", str(resume),
            "--output", str(tmp_path / "plan.yaml"),
        ])

    assert result.exit_code == 0, result.output
    assert "Kubernetes" in result.output


# ---------------------------------------------------------------------------
# `interviewd plan` — validation errors
# ---------------------------------------------------------------------------


def test_plan_command_invalid_type(tmp_path):
    jd = tmp_path / "jd.txt"
    resume = tmp_path / "resume.txt"
    jd.write_text("JD", encoding="utf-8")
    resume.write_text("CV", encoding="utf-8")

    result = runner.invoke(app, [
        "plan", "--jd", str(jd), "--resume", str(resume), "--type", "sales",
    ])
    assert result.exit_code == 1
    assert "Invalid type" in result.output


def test_plan_command_invalid_difficulty(tmp_path):
    jd = tmp_path / "jd.txt"
    resume = tmp_path / "resume.txt"
    jd.write_text("JD", encoding="utf-8")
    resume.write_text("CV", encoding="utf-8")

    result = runner.invoke(app, [
        "plan", "--jd", str(jd), "--resume", str(resume), "--difficulty", "wizard",
    ])
    assert result.exit_code == 1
    assert "Invalid difficulty" in result.output


# ---------------------------------------------------------------------------
# `interviewd interview --plan` — success path
# ---------------------------------------------------------------------------


_QUESTION = Question(
    id="plan_001", text="Describe your K8s experience.",
    tags=[], difficulty="senior", follow_up="",
)

_SESSION = InterviewSession(
    config=InterviewConfig(type="technical", difficulty="senior"),
    turns=[Turn(question=_QUESTION, answer="I used K8s at scale.")],
)

_REPORT = ScoreReport(
    scores=[AnswerScore(
        question_id="plan_001", question_text="Q?", answer="A.",
        star_score=8, relevance_score=9, clarity_score=7,
        feedback="Great.",
    )],
    summary="Excellent.",
)


def test_interview_with_plan_file_uses_plan_questions(tmp_path):
    plan = _make_plan(tmp_path, num_questions=1)
    plan_path = _write_plan_yaml(tmp_path, plan)

    with (
        patch("interviewd.adapters.vad.registry.get_vad_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.stt.registry.get_stt_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.tts.registry.get_tts_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.llm.registry.get_llm_adapter", return_value=MagicMock()),
        patch("interviewd.engine.interview.InterviewEngine.run", new=AsyncMock(return_value=_SESSION)),
        patch("interviewd.scoring.scorer.Scorer.score", new=AsyncMock(return_value=_REPORT)),
        patch("interviewd.config.load_settings", return_value=_mock_settings(tmp_path)),
    ):
        result = runner.invoke(app, ["interview", "--plan", str(plan_path)])

    assert result.exit_code == 0, result.output
    assert "Loaded plan" in result.output
    assert "technical" in result.output
    assert "Session saved" in result.output


def test_interview_with_standard_plan(tmp_path):
    """--plan pointing to config/plans/ works."""
    with (
        patch("interviewd.adapters.vad.registry.get_vad_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.stt.registry.get_stt_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.tts.registry.get_tts_adapter", return_value=MagicMock()),
        patch("interviewd.adapters.llm.registry.get_llm_adapter", return_value=MagicMock()),
        patch("interviewd.engine.interview.InterviewEngine.run", new=AsyncMock(return_value=_SESSION)),
        patch("interviewd.scoring.scorer.Scorer.score", new=AsyncMock(return_value=_REPORT)),
        patch("interviewd.config.load_settings", return_value=_mock_settings(tmp_path)),
    ):
        result = runner.invoke(app, [
            "interview", "--plan", "config/plans/swe_technical_senior.yaml",
        ])

    assert result.exit_code == 0, result.output
    assert "Loaded plan" in result.output


def test_interview_with_missing_plan_file_exits_with_error(tmp_path):
    with patch("interviewd.config.load_settings", return_value=_mock_settings(tmp_path)):
        result = runner.invoke(app, [
            "interview", "--plan", str(tmp_path / "nonexistent.yaml"),
        ])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()
