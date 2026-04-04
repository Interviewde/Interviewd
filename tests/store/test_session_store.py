import pytest

from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.interview import InterviewSession, Turn
from interviewd.scoring.scorer import AnswerScore, ScoreReport
from interviewd.store.session_store import SessionStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return SessionStore(store_dir=str(tmp_path / "sessions"))


def _make_session() -> InterviewSession:
    config = InterviewConfig(
        type="behavioral",
        difficulty="mid",
        num_questions=2,
        time_limit_per_question=120,
        persona="neutral",
        language="en",
    )
    q1 = Question(
        id="q1", text="Tell me about yourself.",
        tags=["intro"], difficulty="entry", follow_up="",
    )
    q2 = Question(
        id="q2", text="Describe a challenge you overcame.",
        tags=["behavioral"], difficulty="mid", follow_up="What did you learn?",
    )
    turns = [
        Turn(question=q1, answer="I am a software engineer."),
        Turn(
            question=q2,
            answer="I debugged a production outage.",
            follow_up_asked=True,
            follow_up_answer="I learned to add better monitoring.",
        ),
    ]
    return InterviewSession(config=config, turns=turns)


def _make_report() -> ScoreReport:
    scores = [
        AnswerScore(
            question_id="q1", question_text="Tell me about yourself.",
            answer="I am a software engineer.",
            star_score=5, relevance_score=7, clarity_score=8,
            feedback="Add more context about your background.",
        ),
        AnswerScore(
            question_id="q2", question_text="Describe a challenge you overcame.",
            answer="I debugged a production outage.\n\nFollow-up: I learned to add better monitoring.",
            star_score=8, relevance_score=9, clarity_score=7,
            feedback="Good STAR structure.",
        ),
    ]
    return ScoreReport(scores=scores, summary="Solid overall performance.")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_returns_uuid_string(store):
    session_id = store.save(_make_session(), _make_report())
    assert isinstance(session_id, str)
    # Basic UUID4 format check
    parts = session_id.split("-")
    assert len(parts) == 5


def test_load_reconstructs_config(store):
    session_id = store.save(_make_session(), _make_report())
    saved = store.load(session_id)

    cfg = saved.interview_session.config
    assert cfg.type == "behavioral"
    assert cfg.difficulty == "mid"
    assert cfg.num_questions == 2
    assert cfg.persona == "neutral"
    assert cfg.language == "en"


def test_load_reconstructs_turns(store):
    session_id = store.save(_make_session(), _make_report())
    saved = store.load(session_id)

    turns = saved.interview_session.turns
    assert len(turns) == 2

    assert turns[0].question.id == "q1"
    assert turns[0].question.tags == ["intro"]
    assert turns[0].answer == "I am a software engineer."
    assert turns[0].follow_up_asked is False
    assert turns[0].follow_up_answer == ""

    assert turns[1].question.id == "q2"
    assert turns[1].follow_up_asked is True
    assert turns[1].follow_up_answer == "I learned to add better monitoring."
    assert turns[1].question.follow_up == "What did you learn?"


def test_load_reconstructs_score_report(store):
    session_id = store.save(_make_session(), _make_report())
    saved = store.load(session_id)

    report = saved.score_report
    assert report.summary == "Solid overall performance."
    assert len(report.scores) == 2

    s1 = next(s for s in report.scores if s.question_id == "q1")
    assert s1.star_score == 5
    assert s1.relevance_score == 7
    assert s1.clarity_score == 8
    assert s1.feedback == "Add more context about your background."

    s2 = next(s for s in report.scores if s.question_id == "q2")
    assert round(s2.overall, 1) == pytest.approx(8.2)


def test_load_raises_for_unknown_id(store):
    with pytest.raises(KeyError, match="not found"):
        store.load("00000000-0000-0000-0000-000000000000")


def test_list_sessions_empty(store):
    assert store.list_sessions() == []


def test_list_sessions_returns_saved(store):
    session_id = store.save(_make_session(), _make_report())
    rows = store.list_sessions()

    assert len(rows) == 1
    assert rows[0]["id"] == session_id
    assert rows[0]["interview_type"] == "behavioral"
    assert rows[0]["difficulty"] == "mid"
    assert rows[0]["avg_overall"] == pytest.approx(7.3)


def test_list_sessions_newest_first(store):
    id1 = store.save(_make_session(), _make_report())
    id2 = store.save(_make_session(), _make_report())
    rows = store.list_sessions()

    assert rows[0]["id"] == id2
    assert rows[1]["id"] == id1


def test_separate_stores_are_isolated(tmp_path):
    store_a = SessionStore(store_dir=str(tmp_path / "a"))
    store_b = SessionStore(store_dir=str(tmp_path / "b"))

    session_id = store_a.save(_make_session(), _make_report())

    with pytest.raises(KeyError):
        store_b.load(session_id)
