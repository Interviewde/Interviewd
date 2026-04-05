# Interviewd

Open source voice agent for mock interview practice — persona-driven, with long-term memory and pluggable backends.

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-org/interviewd.git
cd interviewd
```

### 2. Run the setup script

**macOS / Linux / Git Bash (Windows)**
```bash
bash setup.sh
```

**Windows (PowerShell)**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

The script will:
- Install **uv** (Python toolchain) if missing
- Install **Python 3.11+** via uv if missing
- Install **Node.js** if missing
- Install all Python and frontend dependencies
- Prompt you to configure API keys (saved to `.env`)
- Ask if you want to start the dev server

### 3. Start the dev server (if you skipped it during setup)

```bash
cd frontend && npm run dev:all
```

| Service | URL |
|---|---|
| Web UI | http://localhost:5173 |
| API | http://localhost:8000 |

### API Keys

The default config needs two keys — both have free tiers:

| Key | Provider | Used for |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | Speech-to-text (Whisper) |
| `GOOGLE_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) | LLM (Gemini) |

To reconfigure keys at any time:
```bash
uv run interviewd setup
```

---

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
