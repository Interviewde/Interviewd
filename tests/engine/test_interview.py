from unittest.mock import AsyncMock, MagicMock

import pytest

from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.interview import (
    InterviewEngine,
    InterviewSession,
    Turn,
    detect_end_intent,
)


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
    max_follow_ups: int = 1,
) -> tuple[InterviewEngine, MagicMock, MagicMock]:
    """Build an InterviewEngine with mocked VoiceLoop and LLM.

    llm_responses:   sequential return values for every LLM complete() call.
    listen_responses: sequential return values for voice_loop.listen() calls.

    max_follow_ups defaults to 1 to keep test setup simple (one probe per
    question, matching the old single-follow-up behaviour).

    Returns (engine, mock_voice_loop, mock_llm).
    """
    config = InterviewConfig(
        type="behavioral",
        difficulty="mid",
        num_questions=len(questions),
        persona=persona,
        max_follow_ups=max_follow_ups,
    )

    mock_loop = MagicMock()
    mock_loop.speak = AsyncMock()
    mock_loop.listen = AsyncMock(side_effect=listen_responses)

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(side_effect=llm_responses)

    engine = InterviewEngine(mock_loop, mock_llm, config, questions)
    return engine, mock_loop, mock_llm


# ---------------------------------------------------------------------------
# Turn / Session data models
# ---------------------------------------------------------------------------

def test_turn_defaults():
    q = _make_question()
    turn = Turn(question=q, answer="My answer.")
    assert turn.follow_ups == []
    assert turn.clarifications == []
    assert turn.skipped is False


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
                follow_ups=[("What would you change?", "My follow-up answer.")],
            )
        ],
    )
    t = session.transcript
    assert len(t) == 4
    assert t[2] == {"speaker": "interviewer", "text": "What would you change?"}
    assert t[3] == {"speaker": "candidate", "text": "My follow-up answer."}


def test_session_transcript_with_clarification():
    q = _make_question()
    session = InterviewSession(
        config=InterviewConfig(),
        turns=[
            Turn(
                question=q,
                answer="My answer.",
                clarifications=[("What do you mean by challenge?", "Any work challenge.")],
            )
        ],
    )
    t = session.transcript
    # order: question → clarification (candidate q, agent a) → answer
    assert len(t) == 4
    assert t[0] == {"speaker": "interviewer", "text": q.text}
    assert t[1] == {"speaker": "candidate", "text": "What do you mean by challenge?"}
    assert t[2] == {"speaker": "interviewer", "text": "Any work challenge."}
    assert t[3] == {"speaker": "candidate", "text": "My answer."}


# ---------------------------------------------------------------------------
# Full run — probe returns a follow-up question (not SATISFIED)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_returns_session_with_one_follow_up():
    """With max_follow_ups=1: one probe → LLM returns follow-up Q → ask it."""
    q = _make_question()
    # LLM sequence: greeting, clarification-detect (ANSWER), probe→follow-up Q, closing
    engine, _, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "ANSWER", "Can you be more specific?", "Goodbye!"],
        listen_responses=["My main answer.", "My follow-up answer."],
        max_follow_ups=1,
    )
    session = await engine.run()

    assert len(session.turns) == 1
    turn = session.turns[0]
    assert turn.answer == "My main answer."
    assert len(turn.follow_ups) == 1
    assert turn.follow_ups[0] == ("Can you be more specific?", "My follow-up answer.")
    assert turn.skipped is False


@pytest.mark.asyncio
async def test_run_no_follow_up_when_probe_satisfied():
    """Probe returns SATISFIED → no follow-up asked."""
    q = _make_question()
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "ANSWER", "SATISFIED", "Goodbye!"],
        listen_responses=["My answer."],
        max_follow_ups=1,
    )
    session = await engine.run()
    assert session.turns[0].follow_ups == []
    # listen() called exactly once — no follow-up listen
    mock_loop.listen.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_skips_when_probe_returns_skip():
    """Probe returns SKIP → turn marked skipped, SKIP_MESSAGE spoken."""
    from interviewd.engine.interview import SKIP_MESSAGE
    q = _make_question()
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "ANSWER", "SKIP", "Goodbye!"],
        listen_responses=["I don't know."],
        max_follow_ups=1,
    )
    session = await engine.run()
    assert session.turns[0].skipped is True
    assert session.turns[0].follow_ups == []
    # SKIP_MESSAGE must have been spoken
    spoken = [call.args[0] for call in mock_loop.speak.await_args_list]
    assert SKIP_MESSAGE in spoken


@pytest.mark.asyncio
async def test_run_multiple_follow_ups_stop_at_satisfied():
    """With max_follow_ups=3: LLM probes twice, satisfied on second → 2 follow-ups asked."""
    q = _make_question()
    # LLM: greeting, clarif-detect (ANSWER), probe1→FU Q, clarif-detect FU (ANSWER),
    #       probe2→FU Q, clarif-detect FU2 (ANSWER), probe3→SATISFIED, closing
    # But wait — follow-up listens don't go through _get_answer (no clarif detection).
    # So the LLM sequence for 2 follow-ups with max_follow_ups=3:
    # greeting, clarif-detect main answer (ANSWER), probe1→FU Q,
    # probe2 (after FU answer)→FU Q2,
    # probe3 (after FU2 answer)→SATISFIED, closing = 6 calls
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=[
            "Hello!",           # greeting
            "ANSWER",           # clarif-detect for main answer
            "Tell me more.",    # probe1 → follow-up 1
            "What was the outcome?",  # probe2 → follow-up 2
            "SATISFIED",        # probe3 → done
            "Goodbye!",         # closing
        ],
        listen_responses=["My answer.", "Follow-up 1.", "Follow-up 2."],
        max_follow_ups=3,
    )
    session = await engine.run()
    turn = session.turns[0]
    assert len(turn.follow_ups) == 2
    assert turn.follow_ups[0] == ("Tell me more.", "Follow-up 1.")
    assert turn.follow_ups[1] == ("What was the outcome?", "Follow-up 2.")


@pytest.mark.asyncio
async def test_run_stops_at_max_follow_ups_even_if_not_satisfied():
    """When max_follow_ups reached, engine moves on without probing again."""
    q = _make_question()
    # max_follow_ups=2: probe after main → FU Q, probe after FU1 → FU Q2
    # After FU2 answer, max is reached → no more probing regardless
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=[
            "Hello!",
            "ANSWER",               # clarif-detect
            "Tell me more.",        # probe1 → FU1
            "And what happened?",   # probe2 → FU2
            "Goodbye!",             # closing (probe3 never called)
        ],
        listen_responses=["Main.", "FU1 answer.", "FU2 answer."],
        max_follow_ups=2,
    )
    session = await engine.run()
    turn = session.turns[0]
    assert len(turn.follow_ups) == 2
    # LLM: greeting + clarif + probe1 + probe2 + closing = 5 calls
    assert mock_loop.listen.await_count == 3


@pytest.mark.asyncio
async def test_run_clarification_handled_before_answer():
    """When candidate asks for clarification, engine provides it and re-listens."""
    q = _make_question()
    # LLM: greeting, clarif-detect→CLARIFICATION, generate-clarif,
    #       clarif-detect again→ANSWER (second listen), probe→SATISFIED, closing
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=[
            "Hello!",
            "CLARIFICATION",             # first listen is a clarification
            "The challenge can be anything work-related.",  # clarification response
            "ANSWER",                    # second listen is the actual answer
            "SATISFIED",                 # probe after answer
            "Goodbye!",
        ],
        listen_responses=["What kind of challenge?", "I led a migration."],
        max_follow_ups=1,
    )
    session = await engine.run()
    turn = session.turns[0]
    assert turn.answer == "I led a migration."
    assert len(turn.clarifications) == 1
    assert turn.clarifications[0] == (
        "What kind of challenge?",
        "The challenge can be anything work-related.",
    )
    spoken = [call.args[0] for call in mock_loop.speak.await_args_list]
    assert "The challenge can be anything work-related." in spoken


@pytest.mark.asyncio
async def test_run_multiple_questions():
    questions = [_make_question(id=f"b{i:03d}") for i in range(3)]
    # Q0: probe → follow-up asked; Q1: probe → SATISFIED; Q2: probe → follow-up asked
    # LLM: greeting, (clarif+probe)×3, closing
    llm_responses = [
        "Hi!",
        "ANSWER", "What did you learn?",   # Q0: clarif-detect, probe→FU
        "ANSWER", "SATISFIED",             # Q1: clarif-detect, probe→satisfied
        "ANSWER", "Tell me more.",         # Q2: clarif-detect, probe→FU
        "Bye!",
    ]
    listen_responses = ["a0", "f0", "a1", "a2", "f2"]
    engine, _, _ = _make_engine(
        questions=questions,
        llm_responses=llm_responses,
        listen_responses=listen_responses,
        max_follow_ups=1,
    )
    session = await engine.run()
    assert len(session.turns) == 3
    assert len(session.turns[0].follow_ups) == 1
    assert session.turns[1].follow_ups == []
    assert len(session.turns[2].follow_ups) == 1


# ---------------------------------------------------------------------------
# TTS / speak() call counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_speaks_greeting_question_and_closing():
    q = _make_question()
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "ANSWER", "SATISFIED", "Goodbye!"],
        listen_responses=["My answer."],
        max_follow_ups=1,
    )
    await engine.run()
    # speak: greeting, question text, closing = 3 calls
    assert mock_loop.speak.await_count == 3


@pytest.mark.asyncio
async def test_run_speaks_generated_follow_up_text():
    q = _make_question()
    engine, mock_loop, _ = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "ANSWER", "Can you give a specific example?", "Goodbye!"],
        listen_responses=["Main answer.", "Follow-up answer."],
        max_follow_ups=1,
    )
    await engine.run()
    # speak: greeting, question, generated follow-up text, closing = 4 calls
    assert mock_loop.speak.await_count == 4
    spoken = [call.args[0] for call in mock_loop.speak.await_args_list]
    assert "Can you give a specific example?" in spoken


# ---------------------------------------------------------------------------
# LLM prompt content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_greeting_prompt_includes_config_fields():
    q = _make_question()
    engine, _, mock_llm = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "ANSWER", "SATISFIED", "Bye!"],
        listen_responses=["Answer."],
        persona="friendly",
        max_follow_ups=1,
    )
    await engine.run()
    greeting_call = mock_llm.complete.await_args_list[0]
    prompt = greeting_call.args[0][0]["content"]
    assert "friendly" in prompt
    assert "behavioral" in prompt
    assert "mid" in prompt


@pytest.mark.asyncio
async def test_probe_prompt_includes_persona_and_question():
    q = _make_question()
    engine, _, mock_llm = _make_engine(
        questions=[q],
        llm_responses=["Hello!", "ANSWER", "SATISFIED", "Bye!"],
        listen_responses=["My answer."],
        persona="adversarial",
        max_follow_ups=1,
    )
    await engine.run()
    # LLM calls: greeting(0), clarif-detect(1), probe(2), closing(3)
    probe_call = mock_llm.complete.await_args_list[2]
    prompt = probe_call.args[0][0]["content"]
    assert "adversarial" in prompt or "challenging" in prompt
    assert q.text in prompt


# ---------------------------------------------------------------------------
# detect_end_intent
# ---------------------------------------------------------------------------


async def test_detect_end_intent_returns_false_without_keyword():
    """No keyword in the response — skip the LLM call entirely."""
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="END")  # would say END if called

    result = await detect_end_intent(mock_llm, "I built a recommendation system.")
    assert result is False
    mock_llm.complete.assert_not_called()


async def test_detect_end_intent_confirms_with_llm_when_keyword_present():
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="END")

    result = await detect_end_intent(mock_llm, "I'd like to end the interview now.")
    assert result is True
    mock_llm.complete.assert_awaited_once()


async def test_detect_end_intent_rejects_incidental_mentions():
    """Keyword present but candidate isn't actually asking to end."""
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="CONTINUE")

    result = await detect_end_intent(
        mock_llm, "We had to stop the deployment because of a bug."
    )
    assert result is False
    mock_llm.complete.assert_awaited_once()
