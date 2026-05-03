# AGENTS.md — AI Agent Instructions for Interviewd

## Project Overview

Interviewd is an open-source, voice-based mock interview practice platform written in Python. It runs in two modes:
- **CLI**: Full voice pipeline (microphone in, speaker out) for local practice
- **Web**: React + Vite UI communicating with a FastAPI backend

Core capabilities: scored interviews, practice mode (coaching without scoring), AI-generated interview plans from JD + resume, session history and reporting.

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Package manager | uv |
| CLI | Typer |
| Web framework | FastAPI + uvicorn |
| Frontend | React + Vite (TypeScript) |
| LLM | LiteLLM (Groq/Gemini/OpenAI/Anthropic/Cerebras) |
| STT | Groq Whisper (default), OpenAI Whisper local (fallback) |
| TTS | Edge TTS (default), Piper TTS (offline fallback) |
| VAD | Silero VAD |
| Audio I/O | sounddevice |
| Data validation | Pydantic v2 |
| Config | PyYAML + pydantic-settings |
| ORM / DB | SQLAlchemy + SQLite |
| Testing | pytest + pytest-asyncio |
| Linting | ruff |

## Project Structure

```
interviewd/           # Main Python package
├── config.py         # Pydantic settings: STTConfig, TTSConfig, LLMConfig, InterviewConfig, Settings
├── cli/
│   ├── main.py       # Typer app: interview, plan, setup, report, sessions commands
│   ├── setup.py      # API key wizard
│   └── plan.py       # JD+resume → interview plan
├── engine/
│   ├── interview.py  # InterviewEngine, Turn, InterviewSession, probe_answer(), detect_clarification()
│   └── voice_loop.py # VoiceLoop: VAD→STT→TTS orchestration
├── scoring/
│   └── scorer.py     # Scorer, AnswerScore, ScoreReport
├── store/
│   └── session_store.py  # SessionStore (SQLite), SavedSession
├── data/
│   └── question_bank.py  # QuestionBank, Question
├── adapters/
│   ├── llm/          # LLMAdapter ABC, LiteLLMAdapter, registry
│   ├── stt/          # STTAdapter ABC, GroqSTTAdapter, WhisperLocalSTTAdapter, registry
│   ├── tts/          # TTSAdapter ABC, EdgeTTSAdapter, PiperTTSAdapter, registry
│   └── vad/          # VADAdapter ABC, SileroVADAdapter, registry
├── planner/
│   ├── agent.py      # PlannerAgent: 2-step LLM (analyse + generate questions)
│   ├── models.py     # InterviewPlan, PlannedQuestion, SkillsAnalysis, SkillGap
│   └── ingestion.py  # extract_text(): .pdf/.txt/.md
└── web/
    ├── app.py         # FastAPI app factory, lifespan, CORS
    ├── state.py       # WebInterviewState (in-memory)
    ├── practice_state.py # PracticeSessionState (in-memory)
    ├── adapters.py    # ensure_adapters(): lazy init
    └── api/           # interview.py, practice.py, plans.py, sessions.py

config/
├── default.yaml       # Master config (STT/TTS/LLM/interview params/paths)
├── questions/         # behavioral.yaml, technical.yaml, hr.yaml, system_design.yaml
└── plans/             # swe_technical_senior.yaml, pm_behavioral_mid.yaml

tests/                 # pytest suite, mirrors interviewd/ structure
frontend/              # React + Vite UI
docs/
├── architecture.mmd   # Mermaid system diagram
└── decisions/         # Architecture Decision Records (ADRs 001–005)
```

## Build and Test Commands

```bash
# Install all dependencies
pip install uv
uv sync --all-extras

# Run CLI interview
interviewd interview --type behavioral --difficulty mid --questions 5

# Run web server (localhost:8000)
interviewd-web

# Run frontend dev server (localhost:5173) — separate terminal
cd frontend && npm install && npm run dev

# Run full test suite
uv run pytest

# Run specific tests
uv run pytest tests/engine/ -v
uv run pytest tests/integration/ -v

# Lint and format
uv run ruff check .
uv run ruff format .
```

## Architecture — Key Data Flow

```
CLI interview command
  → load Settings (default.yaml + .env)
  → QuestionBank.pick() → list[Question]
  → VoiceLoop(SileroVAD, GroqSTT, EdgeTTS)
  → InterviewEngine.run()
      ├─ greet (LLM)
      ├─ per question:
      │   ├─ speak question (TTS)
      │   ├─ listen (VAD→STT)
      │   ├─ detect_clarification → if yes: generate_clarification, re-listen
      │   ├─ probe_answer → ProbeResult(follow_up|satisfied|skip)
      │   └─ if follow_up: listen + probe again (up to max_follow_ups)
      └─ closing (LLM)
  → Scorer.score(session) → ScoreReport
  → SessionStore.save(session, report)
  → display report
```

## Adapter Pattern

All pluggable components (LLM, STT, TTS, VAD) follow this pattern:

```python
class MyAdapter(LLMAdapter, provider="my_provider"):
    async def complete(self, messages, stream=True) -> str: ...
    async def stream(self, messages) -> AsyncIterator[str]: ...
```

- `provider=` kwarg in class definition triggers auto-registration via `__init_subclass__`
- `get_llm_adapter(config)` auto-discovers via `pkgutil.iter_modules()` + `importlib`
- **LLM adapters**: open-ended `str` provider → all routed through `LiteLLMAdapter`
- **STT/TTS/VAD adapters**: closed set (`Literal`) — must add a new concrete class for new providers

## Coding Conventions

- **Async-first**: all I/O is `async def`; `sounddevice` blocking calls go in `asyncio.get_event_loop().run_in_executor(None, ...)`
- **Pydantic v2**: use `model_validator`, `field_validator`, `model_dump()`, `model_validate()` — not v1 decorators
- **Prompts**: module-level dict constants, templated with Python `.format()` — no Jinja2 in engine/scoring
- **No direct provider SDK imports** in engine, scoring, or planner — always go through `LLMAdapter.complete()`
- **Config hierarchy**: CLI flags → env vars → YAML → code defaults
- **Scoring weights**: `overall = relevance * 0.4 + star * 0.4 + clarity * 0.2`
- **Line length**: 88 characters (ruff)
- **Target Python**: 3.11+

## Important Constraints

### What IS implemented
- CLI voice interview + scoring + session store
- Web API (REST only — no WebSocket yet)
- React UI with practice mode, full interview, plan upload
- PlannerAgent (JD+resume → tailored question set)
- STT: Groq Whisper + Whisper Local only
- TTS: Edge TTS + Piper only
- LLM: all providers via LiteLLM
- SQLite session persistence

### What is NOT implemented (ignore aspirational docs)
- WebSocket real-time audio streaming
- LangGraph state machine (dependency declared but engine uses plain async Python)
- ChromaDB semantic search
- Deepgram / AssemblyAI STT adapters
- ElevenLabs TTS adapter
- Filler word detector
- OpenTelemetry / Prometheus / Grafana observability
- Rate limit guard
- spaCy NLP (resume parsing uses pypdf only)
- Instructor library for structured outputs (scorer uses plain JSON parsing)

### Web session state
- `WebInterviewState` and `PracticeSessionState` are in-memory only
- `SessionStore.save()` is called only on interview completion
- No distributed session support — single-process deployment assumed

## Environment Setup

Required environment variables (`.env` at project root):
```
GROQ_API_KEY=...          # STT (Groq Whisper) — required for default config
GOOGLE_API_KEY=...        # Gemini LLM (optional)
OPENAI_API_KEY=...        # OpenAI LLM (optional)
ANTHROPIC_API_KEY=...     # Claude LLM (optional)
```

Run `interviewd setup` to configure interactively.

## Testing Notes

- `asyncio_mode = "auto"` in `pyproject.toml` — no need for `@pytest.mark.asyncio`
- Tests under `tests/` mirror `interviewd/` package structure
- Integration tests in `tests/integration/` test full pipeline with mocked voice I/O
- Use `uv run pytest` not bare `pytest`
