# CLAUDE.md — Claude Code Instructions for Interviewd

## Project Overview

Interviewd is an open-source voice-based mock interview practice tool. It supports a CLI mode (full voice pipeline) and a Web mode (React UI + FastAPI backend). Users can run scored interviews, practice informally, and generate tailored interview plans from job descriptions and resumes.

## Architecture Summary

```
Clients (React UI, CLI)
    → Transport (FastAPI REST on :8000)
    → InterviewEngine (async Python)
        → VoiceLoop (sounddevice → SileroVAD → STT → LLM → TTS)
        → LLMAdapter (LiteLLM → Groq/Gemini/OpenAI/Anthropic/Cerebras)
        → Scorer (per-answer STAR + relevance + clarity via LLM)
        → SessionStore (SQLite via SQLAlchemy)
        → QuestionBank (YAML files)
    → PlannerAgent (2-step LLM: analyse JD/resume → generate questions)
```

Adapters (LLM, STT, TTS, VAD) use `__init_subclass__(provider=...)` for auto-registration. All LLM calls go through `LiteLLMAdapter` — no direct Anthropic/Groq/Google SDK calls in engine code.

## Build, Run, and Test Commands

```bash
# Install (requires Python 3.11+, uses uv)
pip install uv
uv sync --all-extras

# Run CLI interview
interviewd interview --type behavioral --difficulty mid

# Run web server
interviewd-web

# Run setup wizard
interviewd setup

# Generate interview plan from JD/resume
interviewd plan --jd path/to/jd.txt --resume path/to/resume.pdf

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/engine/test_interview.py -v

# Lint
uv run ruff check .
uv run ruff format .
```

## Project Structure

```
interviewd/
├── config.py            # Pydantic Settings — STTConfig, TTSConfig, LLMConfig, InterviewConfig
├── cli/                 # Typer CLI (main.py, setup.py, plan.py)
├── engine/              # InterviewEngine, VoiceLoop, prompts
├── scoring/             # Scorer, AnswerScore, ScoreReport
├── store/               # SessionStore (SQLite)
├── data/                # QuestionBank (YAML)
├── adapters/            # ABC + implementations for LLM/STT/TTS/VAD
├── planner/             # PlannerAgent, ingestion, models
└── web/                 # FastAPI app, state, API routers
config/
├── default.yaml         # Master config
├── questions/           # behavioral/technical/hr/system_design YAML
└── plans/               # Pre-built interview plans YAML
tests/                   # pytest suite mirroring package structure
frontend/                # React + Vite UI
```

## Key Patterns

- **Adapter auto-registration**: subclass with `provider="name"` kwarg; `get_*_adapter(config)` discovers via `pkgutil.iter_modules()`
- **All LLM calls**: go through `LiteLLMAdapter.complete()` or `.stream()` — never call provider SDKs directly
- **Prompts**: defined as module-level dict constants, templated with `.format()` — no Jinja2 in engine
- **Async-first**: all I/O is `async`; `sounddevice` runs in thread executor
- **Config hierarchy**: CLI flag → env var → YAML → code default
- **Web state**: in-memory `WebInterviewState` / `PracticeSessionState` dicts keyed by session UUID
- **Scoring weights**: relevance 40% + STAR 40% + clarity 20%

## Claude-Specific Behaviors

### DO
- Use `uv run pytest` (not bare `pytest`) to respect the virtual environment
- Check `interviewd/adapters/*/base.py` before adding a new adapter — follow the ABC + `__init_subclass__` pattern exactly
- Use `LiteLLMAdapter` for any new LLM call; add new providers via litellm model string, not new adapter classes
- Keep prompts as module-level dicts near the functions that use them
- Pydantic v2 syntax throughout (`model_validator`, `field_validator`, not v1 decorators)

### DON'T
- Don't import Anthropic/Groq/Google SDKs directly in engine, scoring, or planner code
- Don't add Jinja2 templating for prompts — `.format()` is the convention
- Don't add LangGraph state machines — `InterviewEngine` is plain async Python; LangGraph is a declared dependency but not used yet
- Don't persist web session state to disk mid-session; `SessionStore.save()` is called only on completion
- Don't add ChromaDB, spaCy, OpenTelemetry, Prometheus, or Grafana — these are in the aspirational architecture diagram but not implemented

## Environment Variables

Required in `.env` (copy from `.env.example`):
- `GROQ_API_KEY` — STT (Groq Whisper) + optional LLM
- `GOOGLE_API_KEY` — Gemini LLM (if using Gemini)
- `OPENAI_API_KEY` — optional
- `ANTHROPIC_API_KEY` — optional

## Test Configuration

- `pytest-asyncio` with `asyncio_mode = "auto"` — all async tests work without `@pytest.mark.asyncio`
- Tests mirror package structure under `tests/`
- Integration tests in `tests/integration/` test full pipeline end-to-end

## Permissions Notes

The `.claude/` directory is in the repo. Standard read/write/bash permissions are sufficient for development.
