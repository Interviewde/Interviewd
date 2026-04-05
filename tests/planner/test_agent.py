"""Tests for interviewd.planner.agent — PlannerAgent with a mocked LLM."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from interviewd.planner.agent import PlannerAgent, _parse_json
from interviewd.planner.models import InterviewPlan


# ---------------------------------------------------------------------------
# _parse_json helper
# ---------------------------------------------------------------------------


def test_parse_json_clean():
    assert _parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_strips_markdown_fence():
    raw = "```json\n{\"a\": 1}\n```"
    assert _parse_json(raw) == {"a": 1}


def test_parse_json_strips_plain_fence():
    raw = "```\n{\"a\": 1}\n```"
    assert _parse_json(raw) == {"a": 1}


def test_parse_json_invalid_returns_empty():
    assert _parse_json("not json at all") == {}


def test_parse_json_empty_string_returns_empty():
    assert _parse_json("") == {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_ANALYSIS_JSON = json.dumps({
    "required_skills": ["Python", "Kubernetes", "API design"],
    "skill_gaps": [
        {"skill": "Kubernetes", "required_level": "high", "resume_level": "missing"},
    ],
    "summary": "Strong Python; no Kubernetes experience.",
})

_QUESTIONS_JSON = json.dumps({
    "questions": [
        {
            "id": "plan_001",
            "text": "Describe your Kubernetes experience.",
            "tags": ["kubernetes"],
            "difficulty": "senior",
            "follow_up": "How did you handle upgrades?",
            "rationale": "K8s is a key gap.",
        },
        {
            "id": "plan_002",
            "text": "Walk me through a Python performance win.",
            "tags": ["python"],
            "difficulty": "senior",
            "follow_up": "",
            "rationale": "Python is a strength.",
        },
    ]
})


def _make_llm(responses: list[str]) -> MagicMock:
    """LLM mock that returns each response string in order."""
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=responses)
    return llm


# ---------------------------------------------------------------------------
# PlannerAgent.run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_run_returns_interview_plan():
    llm = _make_llm([_ANALYSIS_JSON, _QUESTIONS_JSON])
    agent = PlannerAgent(llm)

    plan = await agent.run(
        jd_text="We need a senior Python/K8s engineer.",
        resume_text="3 years Python. No cloud experience.",
        interview_type="technical",
        difficulty="senior",
        num_questions=2,
        jd_source="job.txt",
        resume_source="resume.txt",
    )

    assert isinstance(plan, InterviewPlan)
    assert plan.interview_type == "technical"
    assert plan.difficulty == "senior"
    assert plan.num_questions == 2
    assert plan.jd_source == "job.txt"
    assert plan.resume_source == "resume.txt"


@pytest.mark.asyncio
async def test_agent_run_skills_analysis():
    llm = _make_llm([_ANALYSIS_JSON, _QUESTIONS_JSON])
    plan = await PlannerAgent(llm).run(
        "JD text", "Resume text", "technical", "senior", 2
    )

    assert "Python" in plan.skills_analysis.required_skills
    assert "Kubernetes" in plan.skills_analysis.required_skills
    assert len(plan.skills_analysis.skill_gaps) == 1
    assert plan.skills_analysis.skill_gaps[0].skill == "Kubernetes"
    assert plan.skills_analysis.skill_gaps[0].resume_level == "missing"
    assert "Python" in plan.skills_analysis.summary


@pytest.mark.asyncio
async def test_agent_run_questions():
    llm = _make_llm([_ANALYSIS_JSON, _QUESTIONS_JSON])
    plan = await PlannerAgent(llm).run(
        "JD text", "Resume text", "technical", "senior", 2
    )

    assert len(plan.questions) == 2
    assert plan.questions[0].id == "plan_001"
    assert plan.questions[0].text == "Describe your Kubernetes experience."
    assert plan.questions[0].rationale == "K8s is a key gap."
    assert plan.questions[1].id == "plan_002"


@pytest.mark.asyncio
async def test_agent_makes_exactly_two_llm_calls():
    llm = _make_llm([_ANALYSIS_JSON, _QUESTIONS_JSON])
    await PlannerAgent(llm).run("JD", "Resume", "behavioral", "mid", 3)
    assert llm.complete.call_count == 2


@pytest.mark.asyncio
async def test_agent_truncates_long_input():
    """Input beyond the token budget is silently truncated — LLM is still called."""
    llm = _make_llm([_ANALYSIS_JSON, _QUESTIONS_JSON])
    long_jd = "Python required. " * 1000      # ~4000+ chars
    long_resume = "5 years Python. " * 1000

    plan = await PlannerAgent(llm).run(long_jd, long_resume, "technical", "senior", 2)
    assert plan is not None
    # Verify the prompt passed to the LLM was capped (check first call arg)
    first_call_messages = llm.complete.call_args_list[0][0][0]
    prompt_text = first_call_messages[0]["content"]
    assert len(prompt_text) < 20_000  # well within one context window


@pytest.mark.asyncio
async def test_agent_handles_malformed_llm_response():
    """Gracefully handles garbage LLM output — returns plan with empty fields."""
    llm = _make_llm(["not json", "also not json"])
    plan = await PlannerAgent(llm).run("JD", "Resume", "technical", "mid", 2)

    assert plan.skills_analysis.required_skills == []
    assert plan.skills_analysis.skill_gaps == []
    assert plan.questions == []
