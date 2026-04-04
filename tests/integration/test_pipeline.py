"""Integration tests for the full interview pipeline.

These tests exercise multiple real components together, mocking only at the
hardware/network boundary (mic, speakers, LLM API calls). No tmp YAML files
are used — the real config/questions/ banks are loaded.

Coverage:
  - All question banks load and parse cleanly
  - QuestionBank.pick returns valid questions from each type
  - InterviewEngine + Scorer + SessionStore work together end-to-end
  - A saved session round-trips through the store with full data integrity
  - The CLI interview → report flow works sequentially
"""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interviewd.config import InterviewConfig
from interviewd.data.question_bank import QuestionBank
from interviewd.engine.interview import InterviewEngine, InterviewSession
from interviewd.scoring.scorer import AnswerScore, ScoreReport, Scorer
from interviewd.store.session_store import SessionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BANK_DIR = str(Path(__file__).parents[2] / "config" / "questions")


def _make_llm(responses: list[str]) -> MagicMock:
    """Return a mock LLM adapter that returns responses in sequence."""
    llm = MagicMock()
    llm.complete = AsyncMock(side_effect=responses)
    return llm


def _make_voice_loop(answers: list[str]) -> MagicMock:
    """Return a mock VoiceLoop that 'speaks' silently and returns canned answers."""
    loop = MagicMock()
    loop.speak = AsyncMock()
    loop.listen = AsyncMock(side_effect=answers)
    return loop


# ---------------------------------------------------------------------------
# Question bank loading — real YAML files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("interview_type", ["behavioral", "technical", "hr", "system_design"])
def test_all_question_banks_load(interview_type):
    """Each YAML bank file parses without error and contains at least one question."""
    bank = QuestionBank(_BANK_DIR)
    config = InterviewConfig(type=interview_type, difficulty="staff", num_questions=100)
    questions = bank.pick(config, seed=0)
    assert len(questions) > 0, f"No questions loaded for type '{interview_type}'"


@pytest.mark.parametrize("interview_type,difficulty,expected_min", [
    ("behavioral", "entry", 1),
    ("behavioral", "staff", 5),
    ("technical",  "entry", 1),
    ("technical",  "mid",   3),
    ("hr",         "mid",   3),
    ("hr",         "senior", 5),
    ("system_design", "mid",   1),
    ("system_design", "staff", 5),
])
def test_question_bank_picks_correct_counts(interview_type, difficulty, expected_min):
    """Difficulty filtering returns at least the expected number of eligible questions."""
    bank = QuestionBank(_BANK_DIR)
    config = InterviewConfig(type=interview_type, difficulty=difficulty, num_questions=100)
    questions = bank.pick(config, seed=0)
    assert len(questions) >= expected_min, (
        f"{interview_type}/{difficulty}: got {len(questions)}, want >= {expected_min}"
    )


def test_system_design_has_no_entry_questions():
    """system_design is designed for mid+ — entry difficulty should yield zero picks."""
    bank = QuestionBank(_BANK_DIR)
    config = InterviewConfig(type="system_design", difficulty="entry", num_questions=10)
    questions = bank.pick(config, seed=0)
    assert questions == [], "system_design should have no entry-level questions"


def test_question_ids_are_unique_per_bank():
    """All question IDs within a bank file must be unique."""
    bank = QuestionBank(_BANK_DIR)
    for interview_type in ["behavioral", "technical", "hr", "system_design"]:
        config = InterviewConfig(type=interview_type, difficulty="staff", num_questions=100)
        questions = bank.pick(config, seed=0)
        ids = [q.id for q in questions]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found in '{interview_type}' bank"


def test_all_questions_have_required_fields():
    """Every question in every bank has non-empty id, text, and a valid difficulty."""
    from interviewd.data.question_bank import _DIFFICULTY_RANK
    bank = QuestionBank(_BANK_DIR)
    for interview_type in ["behavioral", "technical", "hr", "system_design"]:
        config = InterviewConfig(type=interview_type, difficulty="staff", num_questions=100)
        for q in bank.pick(config, seed=0):
            assert q.id, f"Empty id in {interview_type}"
            assert q.text, f"Empty text for {q.id} in {interview_type}"
            assert q.difficulty in _DIFFICULTY_RANK, (
                f"Invalid difficulty '{q.difficulty}' for {q.id}"
            )


# ---------------------------------------------------------------------------
# Full pipeline: Engine → Scorer → Store
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_scorer_store_pipeline(tmp_path):
    """Real Engine.run() + Scorer.score() + SessionStore.save/load without hardware."""
    bank = QuestionBank(_BANK_DIR)
    config = InterviewConfig(
        type="behavioral", difficulty="mid", num_questions=2, persona="neutral",
    )
    questions = bank.pick(config, seed=42)

    # LLM responses: greeting + (follow_up decision per question) + closing
    # + (score JSON per question) + summary
    score_json = '{"star_score": 7, "relevance_score": 8, "clarity_score": 6, "feedback": "Good answer."}'
    llm_responses = [
        "Welcome to your interview!",   # greeting
        "NO",                           # follow-up decision Q1
        "NO",                           # follow-up decision Q2
        "Thanks for your time.",        # closing
        score_json,                     # score Q1
        score_json,                     # score Q2
        "Solid performance overall.",   # summary
    ]

    voice_loop = _make_voice_loop(["My answer to Q1.", "My answer to Q2."])
    engine = InterviewEngine(voice_loop, _make_llm(llm_responses[:4]), config, questions)
    session = await engine.run()

    assert isinstance(session, InterviewSession)
    assert len(session.turns) == 2
    assert session.turns[0].answer == "My answer to Q1."

    scorer = Scorer(_make_llm(llm_responses[4:]))
    report = await scorer.score(session)

    assert len(report.scores) == 2
    assert report.average_overall > 0
    assert report.summary == "Solid performance overall."

    store = SessionStore(store_dir=str(tmp_path / "sessions"))
    session_id = store.save(session, report)

    saved = store.load(session_id)
    assert saved.interview_session.config.type == "behavioral"
    assert len(saved.interview_session.turns) == 2
    assert len(saved.score_report.scores) == 2
    assert saved.score_report.summary == "Solid performance overall."


@pytest.mark.asyncio
async def test_pipeline_transcript_is_consistent_with_turns(tmp_path):
    """The transcript property reflects what actually happened in the session."""
    bank = QuestionBank(_BANK_DIR)
    config = InterviewConfig(type="technical", difficulty="mid", num_questions=1)
    questions = bank.pick(config, seed=7)

    score_json = '{"star_score": 5, "relevance_score": 6, "clarity_score": 7, "feedback": "OK."}'
    llm_responses = ["Hi!", "YES", "Thanks!", score_json, "Summary text."]

    voice_loop = _make_voice_loop(["My main answer.", "My follow-up answer."])
    engine = InterviewEngine(voice_loop, _make_llm(llm_responses[:3]), config, questions)
    session = await engine.run()

    transcript = session.transcript
    speakers = [line["speaker"] for line in transcript]

    # With one follow-up: interviewer Q, candidate A, interviewer FU, candidate FU-A
    if session.turns[0].follow_up_asked:
        assert speakers == ["interviewer", "candidate", "interviewer", "candidate"]
    else:
        assert speakers == ["interviewer", "candidate"]


@pytest.mark.asyncio
async def test_pipeline_multiple_types_produce_valid_sessions(tmp_path):
    """Run a minimal pipeline for each question bank type and assert no crashes."""
    bank = QuestionBank(_BANK_DIR)

    for interview_type in ["behavioral", "technical", "hr"]:
        config = InterviewConfig(type=interview_type, difficulty="mid", num_questions=1)
        questions = bank.pick(config, seed=0)

        llm_responses = ["Hello!", "NO", "Bye!", '{"star_score":5,"relevance_score":5,"clarity_score":5,"feedback":"ok"}', "Summary."]
        voice_loop = _make_voice_loop(["My answer."])
        engine = InterviewEngine(voice_loop, _make_llm(llm_responses[:3]), config, questions)
        session = await engine.run()

        scorer = Scorer(_make_llm(llm_responses[3:]))
        report = await scorer.score(session)

        store = SessionStore(store_dir=str(tmp_path / interview_type))
        session_id = store.save(session, report)

        rows = store.list_sessions()
        assert len(rows) == 1
        assert rows[0]["id"] == session_id
        assert rows[0]["interview_type"] == interview_type


# ---------------------------------------------------------------------------
# CLI round-trip: interview → report
# ---------------------------------------------------------------------------


def test_cli_report_after_interview_round_trip(tmp_path):
    """Save a session programmatically, then run the CLI report command against it."""
    from typer.testing import CliRunner

    from interviewd.cli.main import app
    from interviewd.config import InterviewConfig
    from interviewd.data.question_bank import Question
    from interviewd.engine.interview import InterviewSession, Turn
    from interviewd.scoring.scorer import AnswerScore, ScoreReport

    config = InterviewConfig(type="technical", difficulty="senior", num_questions=1)
    question = Question(id="t_int_001", text="Explain dependency injection.", difficulty="senior")
    session = InterviewSession(
        config=config,
        turns=[Turn(question=question, answer="It decouples components via constructor injection.")],
    )
    report = ScoreReport(
        scores=[AnswerScore(
            question_id="t_int_001",
            question_text="Explain dependency injection.",
            answer="It decouples components via constructor injection.",
            star_score=6, relevance_score=8, clarity_score=7,
            feedback="Include a concrete example next time.",
        )],
        summary="Good conceptual grasp; add examples for higher scores.",
    )

    store = SessionStore(store_dir=str(tmp_path / "sessions"))
    session_id = store.save(session, report)

    runner = CliRunner()
    with patch("interviewd.config.load_settings") as mock_settings:
        s = MagicMock()
        s.paths.session_store = str(tmp_path / "sessions")
        mock_settings.return_value = s
        result = runner.invoke(app, ["report", session_id])

    assert result.exit_code == 0, result.output
    assert "technical" in result.output
    assert "Explain dependency injection." in result.output
    assert "It decouples components via constructor injection." in result.output
    assert "Include a concrete example next time." in result.output
    assert "Good conceptual grasp" in result.output
    assert session_id[:8] in result.output
