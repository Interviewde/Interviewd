from dataclasses import dataclass, field

from interviewd.adapters.llm.base import LLMAdapter
from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.voice_loop import VoiceLoop


@dataclass
class Turn:
    """One question–answer pair captured during the interview."""

    question: Question
    answer: str
    follow_up_asked: bool = False
    follow_up_answer: str = ""


@dataclass
class InterviewSession:
    """Completed interview data returned by InterviewEngine.run()."""

    config: InterviewConfig
    turns: list[Turn] = field(default_factory=list)

    @property
    def transcript(self) -> list[dict]:
        """Flat list of {"speaker": ..., "text": ...} dicts — useful for scoring and logging."""
        lines: list[dict] = []
        for turn in self.turns:
            lines.append({"speaker": "interviewer", "text": turn.question.text})
            lines.append({"speaker": "candidate", "text": turn.answer})
            if turn.follow_up_asked:
                lines.append({"speaker": "interviewer", "text": turn.question.follow_up})
                lines.append({"speaker": "candidate", "text": turn.follow_up_answer})
        return lines


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_GREETING_PROMPT = """\
You are a {persona} interviewer conducting a {difficulty}-level {type} interview.
Greet the candidate warmly in one or two sentences, introduce yourself briefly,
and tell them you will ask {num_questions} questions.
Respond with spoken text only — no markdown, no bullet points."""

_FOLLOW_UP_DECISION_PROMPT = """\
The candidate just answered the following interview question:

Question: {question}
Answer: {answer}

Decide whether their answer warrants a follow-up question.
Reply with exactly one word: YES or NO."""

_CLOSING_PROMPT = """\
You are a {persona} interviewer. The interview has just ended.
Thank the candidate sincerely in two or three sentences and let them know
next steps will be shared later.
Respond with spoken text only — no markdown, no bullet points."""


class InterviewEngine:
    """Drives a full interview session using VoiceLoop and an LLM.

    Flow per question:
        1. LLM generates a brief intro/transition, spoken via TTS.
        2. Candidate speaks; VoiceLoop transcribes the answer.
        3. LLM decides if a follow-up is warranted (YES/NO).
        4. If YES and a follow_up text exists on the question, ask it and
           listen again.

    Usage::

        engine = InterviewEngine(voice_loop, llm_adapter, config, questions)
        session = await engine.run()
    """

    def __init__(
        self,
        voice_loop: VoiceLoop,
        llm: LLMAdapter,
        config: InterviewConfig,
        questions: list[Question],
    ):
        self._loop = voice_loop
        self._llm = llm
        self._config = config
        self._questions = questions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _say(self, text: str) -> None:
        """Speak text through TTS."""
        await self._loop.speak(text)

    async def _ask_llm(self, prompt: str) -> str:
        """Call LLM and return response string (no streaming needed for short prompts)."""
        return await self._llm.complete(
            [{"role": "user", "content": prompt}], stream=False
        )

    async def _should_follow_up(self, question: str, answer: str) -> bool:
        """Ask the LLM whether the answer merits a follow-up question."""
        prompt = _FOLLOW_UP_DECISION_PROMPT.format(question=question, answer=answer)
        response = await self._ask_llm(prompt)
        return response.strip().upper().startswith("YES")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> InterviewSession:
        """Run the full interview and return the completed session.

        Returns:
            InterviewSession with all turns populated.
        """
        session = InterviewSession(config=self._config)

        # --- Greeting ---
        greeting_prompt = _GREETING_PROMPT.format(
            persona=self._config.persona,
            difficulty=self._config.difficulty,
            type=self._config.type,
            num_questions=len(self._questions),
        )
        greeting = await self._ask_llm(greeting_prompt)
        await self._say(greeting)

        # --- Questions ---
        for question in self._questions:
            # Speak the question
            await self._say(question.text)

            # Listen for the candidate's answer
            answer = await self._loop.listen()

            turn = Turn(question=question, answer=answer)

            # Follow-up logic: only if the question has a follow_up text
            if question.follow_up:
                ask_follow_up = await self._should_follow_up(question.text, answer)
                if ask_follow_up:
                    turn.follow_up_asked = True
                    await self._say(question.follow_up)
                    turn.follow_up_answer = await self._loop.listen()

            session.turns.append(turn)

        # --- Closing ---
        closing_prompt = _CLOSING_PROMPT.format(
            persona=self._config.persona,
        )
        closing = await self._ask_llm(closing_prompt)
        await self._say(closing)

        return session
