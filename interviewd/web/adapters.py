"""Lazy adapter initialisation for the web layer."""
import structlog

log = structlog.get_logger(__name__)


def ensure_adapters(app_state) -> None:
    """Initialise STT/TTS/LLM adapters on first use. Idempotent."""
    if app_state.llm is not None:
        return

    from interviewd.adapters.llm.registry import get_llm_adapter
    from interviewd.adapters.stt.registry import get_stt_adapter
    from interviewd.adapters.tts.registry import get_tts_adapter
    from interviewd.scoring.scorer import Scorer

    try:
        app_state.stt = get_stt_adapter(app_state.settings.stt)
        log.info("stt adapter ready", provider=app_state.settings.stt.provider)
    except Exception as exc:
        log.error("stt adapter init failed", provider=app_state.settings.stt.provider, error=str(exc))
        raise RuntimeError(
            f"STT adapter failed ({app_state.settings.stt.provider}): {exc}. "
            "Check that the required API key environment variable is set."
        ) from exc

    try:
        app_state.tts = get_tts_adapter(app_state.settings.tts)
        log.info("tts adapter ready", provider=app_state.settings.tts.provider)
    except Exception as exc:
        log.error("tts adapter init failed", provider=app_state.settings.tts.provider, error=str(exc))
        raise RuntimeError(
            f"TTS adapter failed ({app_state.settings.tts.provider}): {exc}."
        ) from exc

    try:
        app_state.llm = get_llm_adapter(app_state.settings.llm)
        log.info("llm adapter ready", provider=app_state.settings.llm.provider, model=app_state.settings.llm.model)
    except Exception as exc:
        log.error("llm adapter init failed", provider=app_state.settings.llm.provider, error=str(exc))
        raise RuntimeError(
            f"LLM adapter failed ({app_state.settings.llm.provider}): {exc}."
        ) from exc

    app_state.scorer = Scorer(app_state.llm)
    log.info("scorer ready")
