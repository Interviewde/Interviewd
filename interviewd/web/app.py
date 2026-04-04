"""FastAPI application for the Interviewd web UI.

Run with:
    uv pip install interviewd[web]
    interviewd-web
    # or directly:
    uv run uvicorn interviewd.web.app:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from interviewd.web.api import interview, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise config and stores at startup; adapters are lazy-loaded on first use.

    Adapters (STT, TTS, LLM) are not created here because they may require API
    keys that aren't configured yet. They are initialised on first request so the
    server starts cleanly and surfaces missing-key errors as HTTP 503s rather than
    a crash at boot time.
    """
    from interviewd.config import load_settings
    from interviewd.data.question_bank import QuestionBank
    from interviewd.store.session_store import SessionStore

    settings = load_settings()
    app.state.settings = settings
    app.state.bank = QuestionBank(settings.paths.question_bank)
    app.state.store = SessionStore(settings.paths.session_store)

    # Adapter slots — filled lazily on first API request.
    app.state.stt = None
    app.state.tts = None
    app.state.llm = None
    app.state.scorer = None

    yield


app = FastAPI(
    title="Interviewd",
    description="Voice mock interview agent — web UI",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the Vite dev server (port 5173) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview.router)
app.include_router(sessions.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


def run() -> None:
    """Entrypoint for the `interviewd-web` CLI script."""
    import uvicorn

    uvicorn.run(
        "interviewd.web.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
