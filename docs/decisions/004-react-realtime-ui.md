# ADR 004 — Web UI: React + FastAPI

**Status:** Accepted  
**Date:** 2026-04-04  
**Deciders:** Abhishek Paliwal

---

## Context

Sprint 1 delivered a fully functional CLI. The next step is a web UI. Two candidate
stacks were evaluated: HTMX + Jinja2 vs. React + TypeScript.

The deciding factor was confirmed roadmap scope: real-time voice LLM APIs (Gemini Live,
OpenAI Realtime) are planned as an optional interview mode in Sprint 3 or Sprint 4.
See [ADR 005](005-dual-path-interview-engine.md) for the dual-path architecture that
supports both the existing pipeline mode and the new live mode.

---

## Why not HTMX

HTMX was the leading candidate until real-time scope was confirmed.

HTMX's `hx-ext="ws"` extension handles **HTML fragment swaps over WebSocket** — text-
based, request-initiated interactions. It cannot cleanly support:

- Continuous binary audio streaming (PCM chunks, bidirectional)
- AudioWorklet-based microphone capture (required for < 100 ms latency in live mode)
- Real-time playback queue management
- Interruption handling (user speaks while AI is mid-response)

These would require a substantial vanilla JS layer alongside HTMX, effectively building
two UI systems in one codebase with no shared conventions. Migrating later — mid-sprint
under delivery pressure — would be more expensive than choosing React now.

For pipeline mode alone, HTMX would have been sufficient (see
[ADR 005](005-dual-path-interview-engine.md) for why pipeline mode is preserved).
The UI decision is driven by the need to support **both modes** in the same frontend.

---

## Decision

**React 18 + TypeScript (Vite) for the frontend. FastAPI for the backend.**

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (Python) |
| Frontend framework | React 18 + TypeScript |
| Build tool | Vite |
| Styling | Tailwind CSS |
| HTTP data fetching | React Query (`@tanstack/react-query`) |
| Real-time transport | WebSocket (FastAPI `WebSocket` ↔ browser `WebSocket`) |
| Audio capture | Web Audio API + `AudioWorklet` |
| Audio playback | Web Audio API `AudioContext` + PCM queue |

---

## Architecture

```
Browser (React)
  │
  │  HTTP (React Query)
  │    GET  /api/sessions             → session list
  │    GET  /api/sessions/{id}        → report
  │    POST /api/interview/setup      → create session, choose mode
  │
  │  WebSocket  (live mode only)
  │    WS   /ws/interview/{id}
  │      → { type: "audio", data: "<base64 PCM>" }
  │      ← { type: "audio_delta", data: "<base64 PCM>" }
  │      ← { type: "text_delta", text: "..." }
  │      ← { type: "turn_complete" }
  │      ← { type: "session_complete", session_id: "..." }
  │
  │  HTTP polling / SSE  (pipeline mode)
  │    POST /api/interview/{id}/answer   multipart audio → next question HTML/JSON
  │
  ▼
FastAPI  (interviewd/web/)
  ├── api/sessions.py
  ├── api/interview.py    → mode-aware: routes to pipeline or live handler
  └── ws/interview.py     → WebSocket handler (live mode)
        └── LiveLLMAdapter (registry, provider set by config)
```

---

## Trade-offs accepted

| Cost | Mitigation |
|------|-----------|
| Node.js as second runtime | One-time install; documented in CONTRIBUTING.md |
| ~300 npm transitive packages | `package-lock.json` pinned; `npm audit` in CI |
| Two dev servers (FastAPI :8000, Vite :5173) | Vite proxy config routes `/api` and `/ws` to FastAPI |
| Higher barrier for Python-only contributors | Backend adapters, scoring, store remain pure Python; UI contribution is opt-in |

---

## Consequences

- The CLI is unaffected — `interviewd` continues to work independently of the web UI.
- The web UI supports both interview modes; the active mode is selected per-session at
  setup time (see ADR 005).
- If live mode is never used, the React frontend functions entirely over HTTP without
  WebSocket connections.
