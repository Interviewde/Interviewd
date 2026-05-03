import traceback
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from interviewd.web.adapters import ensure_adapters
from pydantic import BaseModel

log = structlog.get_logger(__name__)

from interviewd.config import InterviewConfig
from interviewd.engine.interview import (
    END_INTENT_MESSAGE,
    InterviewSession,
    ProbeResult,
    Turn,
    SKIP_MESSAGE,
    detect_clarification,
    detect_end_intent,
    generate_clarification,
    probe_answer,
)
from interviewd.web import state as session_store
from interviewd.web.state import _reset_question_state

router = APIRouter(prefix="/api/interview", tags=["interview"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    type: str = "behavioral"
    difficulty: str = "mid"
    num_questions: int = 5
    persona: str = "neutral"
    # Optional session-wide cap in seconds. 0 (or omitted) disables the cap.
    total_time_limit: int | None = None
    # Optional: load config + questions from a plan instead of the question bank.
    # Value is either a standard plan id (e.g. "swe_technical_senior") or a full
    # plan dict returned by POST /api/plans/generate.
    plan_id: str | None = None
    plan_data: dict | None = None


class QuestionPayload(BaseModel):
    index: int
    total: int
    id: str
    text: str
    is_follow_up: bool = False


class AnswerResponse(BaseModel):
    status: str  # "next_question" | "follow_up" | "complete" | "clarification"
    question: QuestionPayload | None = None
    session_id: str | None = None   # set when status == "complete"
    transcript: str | None = None   # what the STT heard
    clarification_text: str | None = None  # agent's reply to a clarifying question
    skip_message: str | None = None  # spoken when candidate said they don't know
    # Why the interview ended — set alongside status="complete".
    # One of: "completed" | "ended_by_voice" | "timed_out" | "ended_early".
    end_reason: str | None = None
    # Spoken acknowledgement for voice-end / timeout, so the UI can play it
    # before redirecting to the report.
    end_message: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _question_payload(
    state: session_store.WebInterviewState,
    *,
    is_follow_up: bool = False,
    override_text: str = "",
) -> QuestionPayload:
    idx = state.current_index
    q = state.questions[idx]
    return QuestionPayload(
        index=idx,
        total=len(state.questions),
        id=q.id,
        text=override_text if override_text else q.text,
        is_follow_up=is_follow_up,
    )


def _follow_up_payload(
    state: session_store.WebInterviewState,
    follow_up_text: str,
) -> QuestionPayload:
    """Build a payload for a dynamically generated follow-up question."""
    q = state.questions[state.current_index - 1]
    return QuestionPayload(
        index=state.current_index - 1,
        total=len(state.questions),
        id=q.id,
        text=follow_up_text,
        is_follow_up=True,
    )


def _flush_partial_turn(st: session_store.WebInterviewState) -> None:
    """If we're mid follow-up, commit the in-progress main answer + collected
    follow-ups as a final turn so partial work isn't lost on early end."""
    if st.awaiting_follow_up and st.current_main_answer:
        current_q = st.questions[st.current_index - 1]
        st.turns.append(
            Turn(
                question=current_q,
                answer=st.current_main_answer,
                follow_ups=list(st.follow_up_history),
                clarifications=list(st.current_clarifications),
                skipped=False,
            )
        )
        _reset_question_state(st)


async def _finalize_session(
    session_id: str,
    st: session_store.WebInterviewState,
    store,
    scorer,
    completion_status: str,
) -> str | None:
    """Flush any partial state, score, persist, and remove from active state.

    Returns the saved session ID, or None if there was nothing worth saving.
    Used by the normal completion path, voice-end, time-out, and the early-end
    button so they all share identical save semantics.
    """
    _flush_partial_turn(st)
    session_store.remove(session_id)

    if not st.turns:
        return None

    session = InterviewSession(config=st.config, turns=st.turns)
    report = await scorer.score(session)
    return store.save(
        session, report, session_id=session_id, completion_status=completion_status
    )


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

    # --- Plan path ---
    if body.plan_id is not None or body.plan_data is not None:
        from pathlib import Path
        from interviewd.planner.models import InterviewPlan

        if body.plan_data is not None:
            try:
                loaded_plan = InterviewPlan.model_validate(body.plan_data)
            except Exception as exc:
                raise HTTPException(400, f"Invalid plan data: {exc}")
        else:
            plan_path = Path("config/plans") / f"{body.plan_id}.yaml"
            if not plan_path.exists():
                raise HTTPException(404, f"Standard plan '{body.plan_id}' not found.")
            try:
                loaded_plan = InterviewPlan.from_yaml(str(plan_path))
            except Exception as exc:
                raise HTTPException(400, f"Could not load plan: {exc}")

        config = InterviewConfig(
            type=loaded_plan.interview_type,
            difficulty=loaded_plan.difficulty,
            num_questions=loaded_plan.num_questions,
            persona=loaded_plan.persona,
            time_limit_per_question=loaded_plan.time_limit_per_question,
            language=loaded_plan.language,
            mode="pipeline",
            total_time_limit=(
                body.total_time_limit
                if body.total_time_limit is not None
                else settings.interview.total_time_limit
            ),
        )
        questions = loaded_plan.to_questions()

    # --- Manual path ---
    else:
        config = InterviewConfig(
            type=body.type,
            difficulty=body.difficulty,
            num_questions=body.num_questions,
            persona=body.persona,
            time_limit_per_question=settings.interview.time_limit_per_question,
            language=settings.interview.language,
            mode="pipeline",
            total_time_limit=(
                body.total_time_limit
                if body.total_time_limit is not None
                else settings.interview.total_time_limit
            ),
        )
        questions = bank.pick(config)
        if not questions:
            raise HTTPException(
                400,
                f"No questions available for type='{body.type}' difficulty='{body.difficulty}'.",
            )

    session_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    st = session_store.WebInterviewState(
        config=config, questions=questions, started_at=started_at
    )
    session_store.create(session_id, st)

    return {
        "session_id": session_id,
        "question": _question_payload(st).model_dump(),
        "total_time_limit": config.total_time_limit,
        "started_at": started_at.isoformat(),
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

    try:
        audio_bytes = await audio.read()
        content_type = audio.content_type or "audio/webm"
        filename = "audio.webm" if "webm" in content_type else "audio.wav"
        transcript = await stt.transcribe(audio_bytes, filename=filename)
    except Exception as exc:
        log.error("stt transcription failed", error=str(exc), traceback=traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    # ---- Voice-end intent: candidate explicitly asked to stop ----
    try:
        wants_end = await detect_end_intent(llm, transcript)
    except Exception as exc:
        log.error("detect_end_intent failed", error=str(exc), traceback=traceback.format_exc())
        wants_end = False  # never block on this — fall through to normal flow

    if wants_end:
        saved_id = await _finalize_session(
            session_id, st, store, scorer, completion_status="ended_by_voice"
        )
        return AnswerResponse(
            status="complete",
            session_id=saved_id,
            transcript=transcript,
            end_reason="ended_by_voice",
            end_message=END_INTENT_MESSAGE,
        )

    # ---- Session-wide time limit ----
    if (
        st.config.total_time_limit > 0
        and st.started_at is not None
        and (datetime.now(timezone.utc) - st.started_at).total_seconds()
            >= st.config.total_time_limit
    ):
        saved_id = await _finalize_session(
            session_id, st, store, scorer, completion_status="timed_out"
        )
        return AnswerResponse(
            status="complete",
            session_id=saved_id,
            transcript=transcript,
            end_reason="timed_out",
            end_message="We've reached the time limit for this interview. Thank you for your time.",
        )

    skip_msg: str | None = None

    # ---- Follow-up answer path ----
    if st.awaiting_follow_up:
        # Record this follow-up exchange.
        st.follow_up_history.append((st.current_follow_up_question, transcript))
        st.follow_up_count += 1

        current_q = st.questions[st.current_index - 1]
        action = "satisfied"  # default when max_follow_ups already reached
        follow_up_text = ""

        if st.follow_up_count < st.config.max_follow_ups:
            try:
                result = await probe_answer(
                    llm,
                    current_q.text,
                    transcript,
                    list(st.follow_up_history),
                    persona=st.config.persona,
                )
            except Exception as exc:
                log.error("probe_answer (follow-up) failed", error=str(exc), traceback=traceback.format_exc())
                raise HTTPException(status_code=500, detail=f"LLM error during follow-up evaluation: {exc}") from exc
            action = result.action
            follow_up_text = result.follow_up_text

        if action == "follow_up":
            # Another round of probing needed.
            st.current_follow_up_question = follow_up_text
            return AnswerResponse(
                status="follow_up",
                question=_follow_up_payload(st, follow_up_text),
                transcript=transcript,
            )

        # Satisfied, skipped, or max reached — close this turn.
        if action == "skip":
            skip_msg = SKIP_MESSAGE
        turn = Turn(
            question=current_q,
            answer=st.current_main_answer,
            follow_ups=list(st.follow_up_history),
            clarifications=list(st.current_clarifications),
            skipped=(action == "skip"),
        )
        st.turns.append(turn)
        _reset_question_state(st)

    else:
        # ---- Main answer path ----
        current_q = st.questions[st.current_index]

        # Clarification detection — only if below the configured cap.
        if st.clarification_count < st.config.max_clarifications:
            try:
                is_clarification = await detect_clarification(llm, current_q.text, transcript)
            except Exception as exc:
                log.error("clarification detection failed", error=str(exc), traceback=traceback.format_exc())
                raise HTTPException(status_code=500, detail=f"LLM error during clarification detection: {exc}") from exc

            if is_clarification:
                try:
                    clarif_text = await generate_clarification(
                        llm,
                        current_q.text,
                        transcript,
                        persona=st.config.persona,
                    )
                except Exception as exc:
                    log.error("clarification generation failed", error=str(exc), traceback=traceback.format_exc())
                    raise HTTPException(status_code=500, detail=f"LLM error generating clarification: {exc}") from exc

                st.current_clarifications.append((transcript, clarif_text))
                st.clarification_count += 1
                return AnswerResponse(
                    status="clarification",
                    question=_question_payload(st),
                    transcript=transcript,
                    clarification_text=clarif_text,
                )

        # Treat as an actual answer — advance to the next question slot.
        st.current_index += 1
        st.clarification_count = 0

        try:
            result = await probe_answer(
                llm,
                current_q.text,
                transcript,
                [],
                persona=st.config.persona,
            )
        except Exception as exc:
            log.error("probe_answer failed", error=str(exc), traceback=traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"LLM error during answer evaluation: {exc}") from exc

        if result.action == "follow_up" and st.config.max_follow_ups > 0:
            st.awaiting_follow_up = True
            st.current_main_answer = transcript
            st.current_follow_up_question = result.follow_up_text
            return AnswerResponse(
                status="follow_up",
                question=_follow_up_payload(st, result.follow_up_text),
                transcript=transcript,
            )

        # No follow-up (satisfied, skip, or max_follow_ups == 0).
        if result.action == "skip":
            skip_msg = SKIP_MESSAGE
        turn = Turn(
            question=current_q,
            answer=transcript,
            clarifications=list(st.current_clarifications),
            skipped=(result.action == "skip"),
        )
        st.turns.append(turn)
        st.current_clarifications.clear()
        st.clarification_count = 0

    # ---- Check completion ----
    if st.current_index >= len(st.questions) and not st.awaiting_follow_up:
        saved_id = await _finalize_session(
            session_id, st, store, scorer, completion_status="completed"
        )
        return AnswerResponse(
            status="complete",
            session_id=saved_id,
            transcript=transcript,
            skip_message=skip_msg,
            end_reason="completed",
        )

    # ---- Next question ----
    return AnswerResponse(
        status="next_question",
        question=_question_payload(st),
        transcript=transcript,
        skip_message=skip_msg,
    )


@router.post("/{session_id}/end")
async def end_interview(session_id: str, request: Request) -> dict:
    """End an in-progress interview early. Scores partial turns if any exist."""
    try:
        ensure_adapters(request.app.state)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

    st = session_store.get(session_id)
    if st is None:
        raise HTTPException(404, "Session not found or expired.")

    store = request.app.state.store
    scorer = request.app.state.scorer

    saved_id = await _finalize_session(
        session_id, st, store, scorer, completion_status="ended_early"
    )
    return {"session_id": saved_id}


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

    settings = request.app.state.settings
    content_type = "audio/mpeg" if settings.tts.provider == "edge_tts" else "audio/wav"

    return Response(content=audio_bytes, media_type=content_type)
