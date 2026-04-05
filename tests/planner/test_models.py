"""Tests for interviewd.planner.models — InterviewPlan, PlannedQuestion, serialisation."""

import textwrap

import pytest
import yaml

from interviewd.data.question_bank import Question
from interviewd.planner.models import InterviewPlan, PlannedQuestion, SkillGap, SkillsAnalysis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_plan(**overrides) -> InterviewPlan:
    defaults = dict(
        generated_at="2026-04-05T00:00:00+00:00",
        jd_source="job.txt",
        resume_source="resume.txt",
        interview_type="technical",
        difficulty="senior",
        num_questions=2,
        skills_analysis=SkillsAnalysis(
            required_skills=["Python", "Kubernetes"],
            skill_gaps=[
                SkillGap(skill="Kubernetes", required_level="high", resume_level="missing")
            ],
            summary="Strong Python skills; Kubernetes gap.",
        ),
        questions=[
            PlannedQuestion(
                id="plan_001",
                text="Describe your Kubernetes experience.",
                tags=["kubernetes", "infra"],
                difficulty="senior",
                follow_up="How did you handle rolling updates?",
                rationale="JD requires K8s; resume does not mention it.",
            ),
            PlannedQuestion(
                id="plan_002",
                text="Walk me through a Python performance optimisation.",
                tags=["python", "performance"],
                difficulty="senior",
                follow_up="",
                rationale="Python is a strength; probe depth.",
            ),
        ],
    )
    defaults.update(overrides)
    return InterviewPlan(**defaults)


# ---------------------------------------------------------------------------
# PlannedQuestion.to_question
# ---------------------------------------------------------------------------


def test_to_question_returns_question_instance():
    pq = PlannedQuestion(
        id="plan_001", text="Some question?",
        tags=["python"], difficulty="mid", follow_up="Follow up?",
    )
    q = pq.to_question()
    assert isinstance(q, Question)
    assert q.id == "plan_001"
    assert q.text == "Some question?"
    assert q.tags == ["python"]
    assert q.difficulty == "mid"
    assert q.follow_up == "Follow up?"


def test_to_question_drops_rationale():
    pq = PlannedQuestion(
        id="plan_001", text="Q?", difficulty="entry",
        rationale="Some reasoning.",
    )
    q = pq.to_question()
    assert not hasattr(q, "rationale")


# ---------------------------------------------------------------------------
# InterviewPlan.to_questions
# ---------------------------------------------------------------------------


def test_to_questions_returns_list_of_question():
    plan = _make_plan()
    qs = plan.to_questions()
    assert len(qs) == 2
    assert all(isinstance(q, Question) for q in qs)
    assert qs[0].id == "plan_001"
    assert qs[1].id == "plan_002"


# ---------------------------------------------------------------------------
# InterviewPlan.from_yaml
# ---------------------------------------------------------------------------


def _write_plan_yaml(tmp_path, plan: InterviewPlan) -> str:
    path = tmp_path / "plan.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(plan.model_dump(), f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return str(path)


def test_from_yaml_round_trips(tmp_path):
    plan = _make_plan()
    path = _write_plan_yaml(tmp_path, plan)
    loaded = InterviewPlan.from_yaml(path)

    assert loaded.interview_type == "technical"
    assert loaded.difficulty == "senior"
    assert loaded.num_questions == 2
    assert len(loaded.questions) == 2
    assert loaded.questions[0].id == "plan_001"
    assert loaded.skills_analysis.skill_gaps[0].skill == "Kubernetes"


def test_from_yaml_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        InterviewPlan.from_yaml(str(tmp_path / "nonexistent.yaml"))


def test_from_yaml_standard_plan_swe(tmp_path):
    """The shipped standard plan parses cleanly."""
    InterviewPlan.from_yaml("config/plans/swe_technical_senior.yaml")


def test_from_yaml_standard_plan_pm(tmp_path):
    InterviewPlan.from_yaml("config/plans/pm_behavioral_mid.yaml")


# ---------------------------------------------------------------------------
# Validation — invalid values rejected by Pydantic
# ---------------------------------------------------------------------------


def test_invalid_interview_type_raises():
    with pytest.raises(Exception):
        PlannedQuestion(
            id="x", text="Q?", difficulty="mid",
        )
        InterviewPlan(
            generated_at="2026-04-05T00:00:00+00:00",
            interview_type="sales",  # not a valid type
            difficulty="mid",
            num_questions=1,
            skills_analysis=SkillsAnalysis(required_skills=[], skill_gaps=[], summary=""),
            questions=[],
        )


def test_invalid_difficulty_raises():
    with pytest.raises(Exception):
        PlannedQuestion(id="x", text="Q?", difficulty="wizard")
