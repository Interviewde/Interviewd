"""FastAPI application for the Interviewd web UI.

Run with:
    uv pip install interviewd[web]
    interviewd-web
    # or directly:
    uv run uvicorn interviewd.web.app:app --reload
"""
import json
import traceback
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from interviewd.web.api import interview, plans, practice, sessions

log = structlog.get_logger(__name__)


class _ErrorLoggingMiddleware:
    """Raw ASGI middleware — logs every unhandled exception with its full traceback."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            tb = traceback.format_exc()
            log.error(
                "unhandled exception",
                method=scope.get("method", ""),
                path=scope.get("path", ""),
                error=str(exc),
                traceback=tb,
            )
            body = json.dumps({"detail": str(exc), "type": type(exc).__name__}).encode()
            await send({"type": "http.response.start", "status": 500, "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ]})
            await send({"type": "http.response.body", "body": body})


@asynccontextmanager
async def lifespan(app: FastAPI):
    from dotenv import load_dotenv
    from interviewd.config import load_settings
    from interviewd.data.question_bank import QuestionBank
    from interviewd.store.session_store import SessionStore

    load_dotenv(override=False)

    settings = load_settings()
    app.state.settings = settings
    app.state.bank = QuestionBank(settings.paths.question_bank)
    app.state.store = SessionStore(settings.paths.session_store)

    app.state.stt = None
    app.state.tts = None
    app.state.llm = None
    app.state.scorer = None

    log.info("interviewd startup complete", llm=settings.llm.model, stt=settings.stt.provider, tts=settings.tts.provider)
    yield
    log.info("interviewd shutdown")


app = FastAPI(
    title="Interviewd",
    description="Voice mock interview agent — web UI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(_ErrorLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview.router)
app.include_router(plans.router)
app.include_router(practice.router)
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
