# Interviewd

Open source voice agent for mock interview practice — persona-driven, with long-term memory and pluggable backends.

## Architecture

![Architecture](docs/architecture.svg)

> The diagram source lives in [`docs/architecture.mmd`](docs/architecture.mmd) and is auto-rendered to SVG on every push via GitHub Actions.

### Stack at a glance

| Layer | Key Libraries |
|---|---|
| API | `fastapi`, `uvicorn`, `websockets` |
| Voice | `sounddevice`, `silero-vad`, `edge-tts`, `openai-whisper`, `groq` |
| Interview Engine | `langgraph`, `jinja2`, `asyncio` |
| LLM Providers | `groq`, `google-generativeai`, `openai`, `mistralai`, `cerebras-cloud-sdk` |
| Scoring & Feedback | `instructor`, `pydantic` |
| Data | `pyyaml`, `sqlalchemy`, `chromadb`, `pdfplumber`, `spacy` |
| Config | `pydantic-settings`, `pyyaml` |
| Observability | `structlog`, `opentelemetry-python`, `prometheus-client` |
| Frontend | `react`, `vite` |
