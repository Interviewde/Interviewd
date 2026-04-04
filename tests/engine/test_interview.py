from unittest.mock import AsyncMock, MagicMock

import pytest

from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.interview import InterviewEngine, InterviewSession, Turn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_question(id: str = "b001", follow_up: str = "What would you change?") -> Question:
    return Question(
        id=id,
        text="Tell me about a challenge you overcame.",
        tags=["resilience"],
        difficulty="mid",
        follow_up=follow_up,
    )


def _make_engine(
    questions: list[Question],
    llm_responses: list[str],
    listen_responses: list[str],
    *,
    persona: str = "neutral",
) -> tuple[InterviewEngine, MagicMock, MagicMock]:
    """Build an InterviewEngine with mocked VoiceLoop and LLM.

    llm_responses: sequential return values for LLM complete() calls.
    listen_responses: sequential return values for voice_loop.listen() calls.

    Returns (engine, mock_voice_loop, mock_llm).
    """
    config = InterviewConfig(
        type="behavioral",
        difficulty="mid",
        num_questions=len(questions),
        persona=persona,
    )

    mock_loop = MagicMock()
    mock_loop.speak = AsyncMock()
    mock_loop.listen = AsyncMock(side_effect=listen_responses)

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(side_effect=llm_responses)

    engine = InterviewEngine(mock_loop, mock_llm, config, questions)
    return engine, mock_loop, mock_llm


# ---------------------------------------------------------------------------
# Session / Turn data model
# ---------------------------------------------------------------------------

def test_turn_defaults():
    q = _make_question()
    turn = Turn(question=q, answer="My answer.")
    assert not turn.follow_up_asked
    assert turn.follow_up_answer == ""


def test_session_transcript_no_follow_up():
    q = _make_question()
    session = InterviewSession(
        config=InterviewConfig(),
        turns=[Turn(question=q, answer="I overcame it by X.")],
    )
    t = session.transcript
    assert t[0] == {"speaker": "interviewer", "text": q.text}
    assert t[1] == {"speaker": "candidate", "text": "I overcame it by X."}
    assert len(t) == 2


def test_session_transcript_with_follow_up():
    q = _make_question()
    session = InterviewSession(
        config=InterviewConfig(),
        turns=[
            Turn(
                question=q,
                answer="My answer.",
                follow_up_asked=True,
                follow_up_answer="My follow-up answer.",
            )
        ],
    )
    t = session.transcript
    assert len(t) == 4
    assert t[2] == {"speaker": "interviewer", "text": q.follow_up}
    assert t[3] == {"speaker": "candidate", "text": "My follow-up answer."}


# ---------------------------------------------------------------------------
# Full run — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_returns_session_with_correct_turns():
    q = _make_question()
    # LLM calls: greeting, follow-up decision (YES), closing
    engine, _, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello, welcome!", "YES", "Thanks for your time."],
        listen_responses=["My main answer.", "My follow-up answer."],
    )
    session = await engine.run()

    assert isinstance(session, InterviewSession)
    assert len(session.turns) == 1
    turn = session.turns[0]
    assert turn.answer == "My main answer."
    assert turn.follow_up_asked is True
    assert turn.follow_up_answer == "My follow-up answer."


@pytest.mark.asyncio
async def test_run_no_follow_up_when_llm_says_no():
    q = _make_question()
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "NO", "Goodbye!"],
        listen_responses=["My answer."],
    )
    session = await engine.run()
    assert session.turns[0].follow_up_asked is False
    assert session.turns[0].follow_up_answer == ""
    # listen() called exactly once — no follow-up listen
    mock_loop.listen.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_skips_follow_up_when_question_has_none():
    q = Question(id="x001", text="Rate yourself.", difficulty="entry", follow_up="")
    # No follow-up field → LLM follow-up decision should NOT be called
    engine, mock_loop, mock_llm = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "Goodbye!"],
        listen_responses=["Score: 8."],
    )
    session = await engine.run()
    assert session.turns[0].follow_up_asked is False
    # LLM called twice: greeting + closing (no follow-up decision)
    assert mock_llm.complete.await_count == 2
    mock_loop.listen.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_multiple_questions():
    questions = [_make_question(id=f"b{i:03d}") for i in range(3)]
    # LLM: greeting + (decision per question) + closing = 1 + 3 + 1 = 5
    llm_responses = ["Hi!", "YES", "NO", "YES", "Bye!"]
    # listen: main answer + follow-up answer for q0, main for q1, main + follow-up for q2
    listen_responses = ["a0", "f0", "a1", "a2", "f2"]
    engine, _, _ = _make_engine(
        questions=questions,
        llm_responses=llm_responses,
        listen_responses=listen_responses,
    )
    session = await engine.run()
    assert len(session.turns) == 3
    assert session.turns[0].follow_up_asked is True
    assert session.turns[1].follow_up_asked is False
    assert session.turns[2].follow_up_asked is True


# ---------------------------------------------------------------------------
# TTS / speak() call counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_speaks_greeting_question_and_closing():
    q = _make_question()
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "NO", "Goodbye!"],
        listen_responses=["My answer."],
    )
    await engine.run()
    # speak: greeting, question text, closing = 3 calls
    assert mock_loop.speak.await_count == 3


@pytest.mark.asyncio
async def test_run_speaks_follow_up_text_when_triggered():
    q = _make_question()
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "YES", "Goodbye!"],
        listen_responses=["Main answer.", "Follow-up answer."],
    )
    await engine.run()
    # speak: greeting, question, follow_up text, closing = 4 calls
    assert mock_loop.speak.await_count == 4
    spoken_texts = [call.args[0] for call in mock_loop.speak.await_args_list]
    assert q.follow_up in spoken_texts


# ---------------------------------------------------------------------------
# LLM prompt content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_greeting_prompt_includes_config_fields():
    q = _make_question()
    engine, _, mock_llm = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "NO", "Bye!"],
        listen_responses=["Answer."],
        persona="friendly",
    )
    await engine.run()
    greeting_call = mock_llm.complete.await_args_list[0]
    prompt = greeting_call.args[0][0]["content"]
    assert "friendly" in prompt
    assert "behavioral" in prompt
    assert "mid" in prompt
