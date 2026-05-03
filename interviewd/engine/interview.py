import re
from dataclasses import dataclass, field
from typing import Literal

from interviewd.adapters.llm.base import LLMAdapter
from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question
from interviewd.engine.voice_loop import VoiceLoop


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """Return value of probe_answer(): what to do after a candidate's answer."""

    action: Literal["follow_up", "satisfied", "skip"]
    follow_up_text: str = ""  # only populated when action == "follow_up"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Turn:
    """One question–answer pair captured during the interview.

    ``follow_ups``     — (question, answer) pairs for every probing exchange.
    ``clarifications`` — (candidate_question, agent_answer) pairs collected
                         before the candidate gave their main answer.
    ``skipped``        — True when the candidate admitted they don't know.
    """

    question: Question
    answer: str
    follow_ups: list[tuple[str, str]] = field(default_factory=list)
    clarifications: list[tuple[str, str]] = field(default_factory=list)
    skipped: bool = False


@dataclass
class InterviewSession:
    """Completed interview data returned by InterviewEngine.run()."""

    config: InterviewConfig
    turns: list[Turn] = field(default_factory=list)

    @property
    def transcript(self) -> list[dict]:
        """Chronological flat list of {"speaker": ..., "text": ...} dicts."""
        lines: list[dict] = []
        for turn in self.turns:
            lines.append({"speaker": "interviewer", "text": turn.question.text})
            for cand_q, agent_a in turn.clarifications:
                lines.append({"speaker": "candidate", "text": cand_q})
                lines.append({"speaker": "interviewer", "text": agent_a})
            lines.append({"speaker": "candidate", "text": turn.answer})
            for fu_q, fu_a in turn.follow_ups:
                lines.append({"speaker": "interviewer", "text": fu_q})
                lines.append({"speaker": "candidate", "text": fu_a})
        return lines


# ---------------------------------------------------------------------------
# Prompts — defined here so web/api/interview.py can import and reuse them
# ---------------------------------------------------------------------------

PERSONA_STYLE: dict[str, str] = {
    "friendly": "warm and encouraging",
    "neutral": "professional and neutral",
    "adversarial": "direct and challenging — push back on vague answers",
}

SKIP_MESSAGE = (
    "That's completely fine — not every question has an easy answer. Let's move on."
)

END_INTENT_MESSAGE = (
    "Understood — let's wrap up the interview here. Thank you for your time."
)

# Cheap pre-filter for end-of-interview intent. The LLM call only runs when one
# of these tokens shows up, which keeps per-turn latency down.
_END_INTENT_KEYWORDS_RE = re.compile(
    r"\b(end|stop|finish|terminate|wrap|done|quit|exit)\b",
    re.IGNORECASE,
)

_GREETING_PROMPT = """\
You are a {persona} interviewer conducting a {difficulty}-level {type} interview.
Greet the candidate warmly in one or two sentences, introduce yourself briefly,
and tell them you will ask {num_questions} questions.
Respond with spoken text only — no markdown, no bullet points."""

_FOLLOW_UP_PROBE_PROMPT = """\
You are a {persona_style} interviewer assessing a candidate's answer.

Original question: {original_question}
{prior_exchange}\
Candidate's latest answer: {latest_answer}

Decide your next move based ONLY on what the candidate just said. Do not \
follow any pre-written script — react to their actual response.

Reply with EXACTLY one of:
  SATISFIED — the answer is complete, specific, and demonstrates the required competency.
  SKIP — the candidate has clearly admitted they do not know \
(e.g. "I don't know", "I haven't done this", "I'm not sure about that").
  <follow-up question> — a single concise question that DIRECTLY references \
something specific the candidate just said and probes deeper into that point. \
Output the question text only, no label or prefix."""

_DETECT_END_INTENT_PROMPT = """\
You are monitoring a candidate's response during an interview to decide whether
they want to stop the interview entirely.

The candidate said: "{response}"

Are they explicitly requesting to end the interview now (e.g. "I want to end \
the interview", "let's stop", "I'm done with this", "can we wrap up")?
Do NOT treat incidental mentions of stopping/ending things from their work or \
personal life as end-intent (e.g. "I had to stop the deployment", "we ended \
that project last year").
Reply with exactly one word: END or CONTINUE."""

_DETECT_CLARIFICATION_PROMPT = """\
You are evaluating an interview exchange. The interviewer asked:

Question: {question}

The candidate responded:

Response: {response}

Is the candidate asking for clarification about the question (requesting more context, \
constraints, details, or information) rather than actually answering it?
Reply with exactly one word: CLARIFICATION or ANSWER."""

_GENERATE_CLARIFICATION_PROMPT = """\
You are a {persona_style} interviewer conducting an interview. You asked the candidate:

Question: {question}

The candidate asked for clarification:
{candidate_question}

Respond naturally as an interviewer — provide specific, realistic context \
(e.g. scale, constraints, environment, assumptions) that helps them answer. \
Keep it to 2-3 sentences."""

_CLOSING_PROMPT = """\
You are a {persona} interviewer. The interview has just ended.
Thank the candidate sincerely in two or three sentences and let them know
next steps will be shared later.
Respond with spoken text only — no markdown, no bullet points."""


# ---------------------------------------------------------------------------
# Shared async helpers — also imported by web/api/interview.py
# ---------------------------------------------------------------------------


async def probe_answer(
    llm: LLMAdapter,
    original_question: str,
    latest_answer: str,
    prior_followups: list[tuple[str, str]],
    *,
    persona: str = "neutral",
) -> ProbeResult:
    """Evaluate a candidate's answer and decide what to do next.

    Uses the LLM to return one of three actions:
    - "follow_up": answer needs probing; follow_up_text holds the question.
    - "satisfied": answer is complete; move to next question.
    - "skip": candidate admitted they don't know; acknowledge and move on.

    The follow-up question is generated dynamically from the candidate's
    actual answer — no static "probe angle" hint is used, since that
    anchored the LLM toward pre-written questions instead of responding
    to what the candidate said.
    """
    persona_style = PERSONA_STYLE.get(persona, "professional and neutral")

    if prior_followups:
        lines = ["Prior exchange:"]
        for i, (q, a) in enumerate(prior_followups, 1):
            lines.append(f"  Follow-up {i}: {q}")
            lines.append(f"  Response {i}: {a}")
        prior_exchange = "\n".join(lines) + "\n"
    else:
        prior_exchange = ""

    prompt = _FOLLOW_UP_PROBE_PROMPT.format(
        persona_style=persona_style,
        original_question=original_question,
        prior_exchange=prior_exchange,
        latest_answer=latest_answer,
    )
    response = await llm.complete([{"role": "user", "content": prompt}], stream=False)
    text = response.strip()
    upper = text.upper()

    if upper.startswith("SATISFIED"):
        return ProbeResult(action="satisfied")
    if upper.startswith("SKIP"):
        return ProbeResult(action="skip")
    return ProbeResult(action="follow_up", follow_up_text=text)


async def detect_clarification(llm: LLMAdapter, question: str, response: str) -> bool:
    """Return True if the candidate is asking for clarification, not answering."""
    prompt = _DETECT_CLARIFICATION_PROMPT.format(question=question, response=response)
    result = await llm.complete([{"role": "user", "content": prompt}], stream=False)
    return result.strip().upper().startswith("CLARIFICATION")


async def detect_end_intent(llm: LLMAdapter, response: str) -> bool:
    """Return True if the candidate wants to end the interview now.

    Uses a regex pre-filter so the LLM is only consulted when an end-related
    keyword shows up in the transcript. This avoids paying for an extra LLM
    call on every turn while still catching genuine end-intent phrasings.
    """
    if not _END_INTENT_KEYWORDS_RE.search(response):
        return False
    prompt = _DETECT_END_INTENT_PROMPT.format(response=response)
    result = await llm.complete([{"role": "user", "content": prompt}], stream=False)
    return result.strip().upper().startswith("END")


async def generate_clarification(
    llm: LLMAdapter,
    question: str,
    candidate_question: str,
    *,
    persona: str = "neutral",
) -> str:
    """Generate an interviewer clarification response."""
    persona_style = PERSONA_STYLE.get(persona, "professional and neutral")
    prompt = _GENERATE_CLARIFICATION_PROMPT.format(
        persona_style=persona_style,
        question=question,
        candidate_question=candidate_question,
    )
    return await llm.complete([{"role": "user", "content": prompt}], stream=False)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class InterviewEngine:
    """Drives a full interview session using VoiceLoop and an LLM.

    Per-question flow:
        1. Speak the question.
        2. Listen — loop back if the candidate asks for clarification (up to
           config.max_clarifications times).
        3. Probe the LLM: SATISFIED → next question, SKIP → acknowledge and
           move on, follow-up question → speak it, listen, probe again.
        4. Repeat step 3 up to config.max_follow_ups times.

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

    async def _say(self, text: str) -> None:
        await self._loop.speak(text)

    async def _ask_llm(self, prompt: str) -> str:
        return await self._llm.complete(
            [{"role": "user", "content": prompt}], stream=False
        )

    async def _get_answer(
        self, question_text: str
    ) -> tuple[str, list[tuple[str, str]]]:
        """Listen until we receive an actual answer, handling clarifications.

        Returns (answer, clarifications) where clarifications is a list of
        (candidate_question, agent_answer) pairs collected beforehand.
        """
        clarifications: list[tuple[str, str]] = []
        while True:
            response = await self._loop.listen()
            if (
                len(clarifications) < self._config.max_clarifications
                and await detect_clarification(self._llm, question_text, response)
            ):
                clarif_response = await generate_clarification(
                    self._llm,
                    question_text,
                    response,
                    persona=self._config.persona,
                )
                clarifications.append((response, clarif_response))
                await self._say(clarif_response)
            else:
                return response, clarifications

    async def run(self) -> InterviewSession:
        """Run the full interview and return the completed session."""
        session = InterviewSession(config=self._config)

        greeting = await self._ask_llm(
            _GREETING_PROMPT.format(
                persona=self._config.persona,
                difficulty=self._config.difficulty,
                type=self._config.type,
                num_questions=len(self._questions),
            )
        )
        await self._say(greeting)

        for question in self._questions:
            await self._say(question.text)
            answer, clarifications = await self._get_answer(question.text)
            turn = Turn(question=question, answer=answer, clarifications=clarifications)

            for _ in range(self._config.max_follow_ups):
                latest = turn.follow_ups[-1][1] if turn.follow_ups else answer
                result = await probe_answer(
                    self._llm,
                    question.text,
                    latest,
                    turn.follow_ups,
                    persona=self._config.persona,
                )
                if result.action == "skip":
                    await self._say(SKIP_MESSAGE)
                    turn.skipped = True
                    break
                if result.action == "satisfied":
                    break
                await self._say(result.follow_up_text)
                # Follow-up exchanges don't recurse into clarification detection.
                follow_up_answer = await self._loop.listen()
                turn.follow_ups.append((result.follow_up_text, follow_up_answer))

            session.turns.append(turn)

        closing = await self._ask_llm(
            _CLOSING_PROMPT.format(persona=self._config.persona)
        )
        await self._say(closing)

        return session
