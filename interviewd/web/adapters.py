"""Lazy adapter initialisation for the web layer.

Adapters are not created at server startup because they may require API keys
that aren't configured. _ensure_adapters() is called by routes on first use
and is idempotent — subsequent calls are a cheap null-check.
"""


def ensure_adapters(app_state) -> None:
    """Initialise STT/TTS/LLM adapters on first use.

    Raises RuntimeError with a human-readable message if an adapter fails to
    initialise (e.g. missing API key), which the route converts to HTTP 503.
    """
    if app_state.llm is not None:
        return  # already initialised

    from interviewd.adapters.llm.registry import get_llm_adapter
    from interviewd.adapters.stt.registry import get_stt_adapter
    from interviewd.adapters.tts.registry import get_tts_adapter
    from interviewd.scoring.scorer import Scorer

    try:
        app_state.stt = get_stt_adapter(app_state.settings.stt)
    except Exception as exc:
        raise RuntimeError(
            f"STT adapter failed ({app_state.settings.stt.provider}): {exc}. "
            "Check that the required API key environment variable is set."
        ) from exc

    try:
        app_state.tts = get_tts_adapter(app_state.settings.tts)
    except Exception as exc:
        raise RuntimeError(
            f"TTS adapter failed ({app_state.settings.tts.provider}): {exc}."
        ) from exc

    try:
        app_state.llm = get_llm_adapter(app_state.settings.llm)
    except Exception as exc:
        raise RuntimeError(
            f"LLM adapter failed ({app_state.settings.llm.provider}): {exc}."
        ) from exc

    app_state.scorer = Scorer(app_state.llm)
