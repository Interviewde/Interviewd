import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.interview import InterviewSession, Turn
from interviewd.scoring.scorer import AnswerScore, ScoreReport, Scorer, _parse_scores


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_question(id: str = "b001") -> Question:
    return Question(
        id=id,
        text="Tell me about a challenge.",
        difficulty="mid",
        follow_up="What would you do differently?",
    )


def _make_turn(answer: str = "I overcame it by X.", follow_up: bool = False) -> Turn:
    q = _make_question()
    return Turn(
        question=q,
        answer=answer,
        follow_up_asked=follow_up,
        follow_up_answer="I'd do Y next time." if follow_up else "",
    )


def _make_session(turns: list[Turn]) -> InterviewSession:
    return InterviewSession(config=InterviewConfig(), turns=turns)


def _score_response(star: int = 7, relevance: int = 8, clarity: int = 6, feedback: str = "Good.") -> str:
    return json.dumps({
        "star_score": star,
        "relevance_score": relevance,
        "clarity_score": clarity,
        "feedback": feedback,
    })


def _make_llm(responses: list[str]) -> MagicMock:
    mock = MagicMock()
    mock.complete = AsyncMock(side_effect=responses)
    return mock


# ---------------------------------------------------------------------------
# _parse_scores
# ---------------------------------------------------------------------------

def test_parse_scores_clean_json():
    raw = _score_response(star=9, relevance=8, clarity=7, feedback="Strong.")
    result = _parse_scores(raw)
    assert result == {"star_score": 9, "relevance_score": 8, "clarity_score": 7, "feedback": "Strong."}


def test_parse_scores_strips_markdown_fences():
    raw = "```json\n" + _score_response(star=5, relevance=6, clarity=4) + "\n```"
    result = _parse_scores(raw)
    assert result["star_score"] == 5
    assert result["relevance_score"] == 6


def test_parse_scores_bad_json_returns_zeros():
    result = _parse_scores("not json at all")
    assert result == {"star_score": 0, "relevance_score": 0, "clarity_score": 0, "feedback": ""}


def test_parse_scores_missing_fields_default_zero():
    result = _parse_scores('{"star_score": 5}')
    assert result["relevance_score"] == 0
    assert result["clarity_score"] == 0
    assert result["feedback"] == ""


# ---------------------------------------------------------------------------
# AnswerScore
# ---------------------------------------------------------------------------

def test_answer_score_overall_weighted():
    s = AnswerScore(
        question_id="b001",
        question_text="Q",
        answer="A",
        star_score=10,
        relevance_score=10,
        clarity_score=0,
        feedback="",
    )
    # 10*0.4 + 10*0.4 + 0*0.2 = 8.0
    assert s.overall == 8.0


def test_answer_score_overall_mixed():
    s = AnswerScore(
        question_id="b001", question_text="Q", answer="A",
        star_score=6, relevance_score=8, clarity_score=5, feedback="",
    )
    # 8*0.4 + 6*0.4 + 5*0.2 = 3.2 + 2.4 + 1.0 = 6.6
    assert s.overall == 6.6


# ---------------------------------------------------------------------------
# ScoreReport aggregates
# ---------------------------------------------------------------------------

def test_score_report_averages():
    scores = [
        AnswerScore(question_id="b001", question_text="Q", answer="A",
                    star_score=8, relevance_score=6, clarity_score=4, feedback=""),
        AnswerScore(question_id="b002", question_text="Q", answer="A",
                    star_score=4, relevance_score=10, clarity_score=6, feedback=""),
    ]
    report = ScoreReport(scores=scores)
    assert report.average_star == 6.0
    assert report.average_relevance == 8.0
    assert report.average_clarity == 5.0


def test_score_report_empty():
    report = ScoreReport()
    assert report.average_overall == 0.0
    assert report.average_star == 0.0


# ---------------------------------------------------------------------------
# Scorer.score()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_single_turn():
    turn = _make_turn()
    session = _make_session([turn])
    llm = _make_llm([
        _score_response(star=7, relevance=8, clarity=9, feedback="Great STAR."),
        "You performed well overall.",  # summary
    ])
    scorer = Scorer(llm)
    report = await scorer.score(session)

    assert len(report.scores) == 1
    s = report.scores[0]
    assert s.star_score == 7
    assert s.relevance_score == 8
    assert s.clarity_score == 9
    assert s.feedback == "Great STAR."
    assert report.summary == "You performed well overall."


@pytest.mark.asyncio
async def test_score_multiple_turns():
    turns = [_make_turn(), _make_turn(answer="Different answer.")]
    session = _make_session(turns)
    llm_responses = [
        _score_response(star=6, relevance=7, clarity=5),
        _score_response(star=8, relevance=9, clarity=7),
        "Good session.",  # summary
    ]
    scorer = Scorer(_make_llm(llm_responses))
    report = await scorer.score(session)

    assert len(report.scores) == 2
    assert report.summary == "Good session."
    # LLM called once per turn + once for summary = 3
    scorer._llm.complete.assert_awaited()
    assert scorer._llm.complete.await_count == 3


@pytest.mark.asyncio
async def test_score_appends_follow_up_to_answer():
    turn = _make_turn(answer="Main answer.", follow_up=True)
    session = _make_session([turn])
    llm = _make_llm([_score_response(), "Summary."])
    scorer = Scorer(llm)
    await scorer.score(session)

    # The first LLM call (scoring) should receive the combined answer
    score_call_prompt = scorer._llm.complete.await_args_list[0].args[0][0]["content"]
    assert "Main answer." in score_call_prompt
    assert "Follow-up: I'd do Y next time." in score_call_prompt


@pytest.mark.asyncio
async def test_score_summary_includes_average():
    turn = _make_turn()
    session = _make_session([turn])
    llm = _make_llm([_score_response(star=10, relevance=10, clarity=10), "Perfect score."])
    scorer = Scorer(llm)
    report = await scorer.score(session)

    # Check summary prompt contains the average
    summary_call_prompt = scorer._llm.complete.await_args_list[1].args[0][0]["content"]
    assert "10.0" in summary_call_prompt


@pytest.mark.asyncio
async def test_score_bad_llm_response_does_not_crash():
    """Graceful fallback when LLM returns unparseable JSON."""
    turn = _make_turn()
    session = _make_session([turn])
    llm = _make_llm(["totally not json", "Summary anyway."])
    scorer = Scorer(llm)
    report = await scorer.score(session)

    assert report.scores[0].star_score == 0
    assert report.scores[0].feedback == ""
    assert report.summary == "Summary anyway."
