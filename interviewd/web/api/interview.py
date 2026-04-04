import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from interviewd.web.adapters import ensure_adapters
from pydantic import BaseModel

from interviewd.config import InterviewConfig
from interviewd.engine.interview import InterviewSession, Turn
from interviewd.web import state as session_store

router = APIRouter(prefix="/api/interview", tags=["interview"])

# Reuse the same follow-up prompt as InterviewEngine so behaviour is consistent.
_FOLLOW_UP_DECISION_PROMPT = """\
The candidate just answered the following interview question:

Question: {question}
Answer: {answer}

Decide whether their answer warrants a follow-up question.
Reply with exactly one word: YES or NO."""


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    type: str = "behavioral"
    difficulty: str = "mid"
    num_questions: int = 5
    persona: str = "neutral"


class QuestionPayload(BaseModel):
    index: int
    total: int
    id: str
    text: str
    is_follow_up: bool = False


class AnswerResponse(BaseModel):
    status: str          # "next_question" | "follow_up" | "complete"
    question: QuestionPayload | None = None
    session_id: str | None = None  # set when status == "complete"
    transcript: str | None = None  # what the STT heard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _question_payload(
    state: session_store.WebInterviewState,
    *,
    is_follow_up: bool = False,
) -> QuestionPayload:
    idx = state.current_index
    q = state.questions[idx]
    return QuestionPayload(
        index=idx,
        total=len(state.questions),
        id=q.id,
        text=q.follow_up if is_follow_up else q.text,
        is_follow_up=is_follow_up,
    )


async def _should_follow_up(llm, question: str, answer: str) -> bool:
    prompt = _FOLLOW_UP_DECISION_PROMPT.format(question=question, answer=answer)
    response = await llm.complete([{"role": "user", "content": prompt}], stream=False)
    return response.strip().upper().startswith("YES")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start")
async def start_interview(body: StartRequest, request: Request) -> dict:
    """Validate params, pick questions, create session state, return first question."""
    try:
        ensure_adapters(request.app.state)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    _VALID_TYPES = ("behavioral", "technical", "hr", "system_design")
    _VALID_DIFFICULTIES = ("entry", "mid", "senior", "staff")

    if body.type not in _VALID_TYPES:
        raise HTTPException(400, f"Invalid type '{body.type}'. Choose: {_VALID_TYPES}")
    if body.difficulty not in _VALID_DIFFICULTIES:
        raise HTTPException(400, f"Invalid difficulty '{body.difficulty}'. Choose: {_VALID_DIFFICULTIES}")

    settings = request.app.state.settings
    bank = request.app.state.bank

    config = InterviewConfig(
        type=body.type,
        difficulty=body.difficulty,
        num_questions=body.num_questions,
        persona=body.persona,
        time_limit_per_question=settings.interview.time_limit_per_question,
        language=settings.interview.language,
        mode="pipeline",
    )

    questions = bank.pick(config)
    if not questions:
        raise HTTPException(
            400,
            f"No questions available for type='{body.type}' difficulty='{body.difficulty}'.",
        )

    session_id = str(uuid.uuid4())
    st = session_store.WebInterviewState(config=config, questions=questions)
    session_store.create(session_id, st)

    return {
        "session_id": session_id,
        "question": _question_payload(st).model_dump(),
    }


@router.post("/{session_id}/answer")
async def submit_answer(
    session_id: str,
    request: Request,
    audio: UploadFile = File(...),
) -> AnswerResponse:
    """Receive recorded audio, transcribe, decide follow-up, advance state."""
    try:
        ensure_adapters(request.app.state)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    st = session_store.get(session_id)
    if st is None:
        raise HTTPException(404, "Session not found or expired.")

    stt = request.app.state.stt
    llm = request.app.state.llm
    store = request.app.state.store
    scorer = request.app.state.scorer

    audio_bytes = await audio.read()

    # Determine filename for format hint (browser sends webm)
    content_type = audio.content_type or "audio/webm"
    filename = "audio.webm" if "webm" in content_type else "audio.wav"

    transcript = await stt.transcribe(audio_bytes, filename=filename)

    # ---- Follow-up answer path ----
    if st.awaiting_follow_up:
        # Complete the current turn with the follow-up answer
        turn = Turn(
            question=st.questions[st.current_index - 1],
            answer=st.current_main_answer,
            follow_up_asked=True,
            follow_up_answer=transcript,
        )
        st.turns.append(turn)
        st.awaiting_follow_up = False
        st.current_main_answer = ""
        # Fall through to check if interview is complete

    else:
        # ---- Main answer path ----
        current_q = st.questions[st.current_index]
        st.current_index += 1

        # Ask LLM if a follow-up is warranted (only if the question has one)
        if current_q.follow_up:
            ask_follow_up = await _should_follow_up(llm, current_q.text, transcript)
        else:
            ask_follow_up = False

        if ask_follow_up:
            st.awaiting_follow_up = True
            st.current_main_answer = transcript
            return AnswerResponse(
                status="follow_up",
                question=QuestionPayload(
                    index=st.current_index - 1,
                    total=len(st.questions),
                    id=current_q.id,
                    text=current_q.follow_up,
                    is_follow_up=True,
                ),
                transcript=transcript,
            )
        else:
            turn = Turn(question=current_q, answer=transcript)
            st.turns.append(turn)

    # ---- Check completion ----
    if st.current_index >= len(st.questions) and not st.awaiting_follow_up:
        # Score and persist
        session = InterviewSession(config=st.config, turns=st.turns)
        report = await scorer.score(session)
        saved_id = store.save(session, report)
        session_store.remove(session_id)
        return AnswerResponse(status="complete", session_id=saved_id, transcript=transcript)

    # ---- Next question ----
    return AnswerResponse(
        status="next_question",
        question=_question_payload(st),
        transcript=transcript,
    )


@router.get("/tts")
async def synthesize_speech(text: str, request: Request):
    """Return TTS audio bytes for a given text string."""
    from fastapi.responses import Response

    try:
        ensure_adapters(request.app.state)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    tts = request.app.state.tts
    audio_bytes = await tts.synthesize(text)

    # edge_tts produces MP3; piper produces WAV
    settings = request.app.state.settings
    content_type = "audio/mpeg" if settings.tts.provider == "edge_tts" else "audio/wav"

    return Response(content=audio_bytes, media_type=content_type)
