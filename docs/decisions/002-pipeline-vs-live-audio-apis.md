# ADR 002 — Pipeline Architecture vs Live Audio APIs

## Status
Accepted

## Context

Building a voice-based interview agent requires handling the full audio conversation
loop: capturing speech, understanding it, generating a response, and speaking it back.
Two fundamentally different architectural approaches exist for this.

### Option A — Modular pipeline (chosen)

```
Mic → VAD → STT → LLM (text in / text out) → TTS → Speaker
```

Each stage is a discrete, independently swappable adapter:

| Stage | Built-in options | Local option |
|-------|-----------------|--------------|
| VAD | Silero | ✅ runs on CPU |
| STT | Groq Whisper, Whisper local | ✅ Whisper local |
| LLM | Any LiteLLM-supported model | ✅ Ollama (Sprint 2) |
| TTS | Edge TTS, Piper | ✅ Piper |

### Option B — Live audio APIs

Vendors including OpenAI (GPT-4o Realtime), Google (Gemini Live), Amazon (Nova Sonic),
and ElevenLabs (Conversational AI) offer end-to-end APIs that accept a raw audio stream
and return a raw audio stream. These collapse the entire pipeline — VAD, STT, LLM, and
TTS — into a single WebSocket session.

## Decision

Use the modular pipeline (Option A). Live audio APIs are explicitly out of scope for
the current implementation. A future integration path is described below.

## Reasoning

### 1 — Stability

Live audio APIs are at an early stage of maturity. As of April 2025, all major
offerings are in public beta or recently GA, with breaking changes to session
management, turn-detection parameters, and event schemas still shipping regularly.
Text-based LLMs have years of production usage and a stable, battle-tested API surface.
The individual STT and TTS markets are similarly mature. Grounding Interviewd on
stable primitives means the framework does not inherit the churn of any single vendor's
beta roadmap.

### 2 — Accuracy

Live audio LLMs currently produce more transcription and reasoning errors than a
dedicated STT model feeding text to a dedicated text LLM. Combining understanding and
generation in a single audio-to-audio model is harder than specialised models for each
task. For an interview coach, factual accuracy, coherent follow-up questions, and
reliable scoring matter more than slightly lower latency.

### 3 — Cost and accessibility

None of the live audio APIs offer a free tier sufficient for realistic usage, nor can
they be run locally on consumer hardware. The modular pipeline supports fully free,
fully offline operation:

| Component | Free option | Requires internet |
|-----------|------------|-------------------|
| VAD | Silero (CPU) | No |
| STT | Whisper local | No |
| LLM | Ollama (Sprint 2) | No |
| TTS | Piper | No |

A first-time contributor or student should be able to run the full voice loop with no
API keys, no cloud account, and no GPU. Live audio APIs rule that out entirely.

### 4 — Testability and debuggability

A modular pipeline produces discrete, inspectable outputs at each stage. A failing
interaction can be diagnosed at the VAD level (silence detection), STT level
(transcript), LLM level (response text), or TTS level (audio), in isolation.
Live audio APIs expose only the final audio output; when something goes wrong,
the failure surface is opaque and much harder to reproduce in a unit test.

### 5 — Swappability and vendor independence

Each stage in the pipeline is behind an adapter interface. Switching STT from Groq to
Deepgram, or LLM from Gemini to Claude, is a one-line change in `config/default.yaml`.
A live audio API session is an indivisible unit — replacing the provider means
re-implementing the entire audio loop against a different vendor-specific protocol.

## Trade-offs

### What the pipeline gives up

| Property | Pipeline | Live audio API |
|----------|----------|----------------|
| Turn latency | Higher — multiple serial round trips | Lower — single streaming session |
| Interruption handling | Not native (requires custom VAD logic) | Built-in |
| Prosody and emotion | Limited by TTS model | Can be richer and more natural |
| API surface | Four separate services to integrate | One WebSocket |

Latency is the most significant trade-off. A pipeline round trip (VAD → STT → LLM →
TTS) typically adds 1–3 seconds of latency compared to live audio APIs, which can
respond in under a second. For a structured mock interview — where the interviewer
typically waits for the candidate to finish speaking before responding — this is
acceptable. It would be more limiting for freeform conversation or rapid back-and-forth.

### What the pipeline keeps

- Zero-cost local operation
- Per-component unit tests and mock injection
- Independent upgrades: swap the STT model without touching the LLM or TTS
- Works offline: useful for low-connectivity environments or privacy-sensitive deployments
- Transparent intermediate state: transcripts and LLM responses are readable text at
  every stage, which is also needed for scoring and session replay

## Future path

Live audio APIs are not permanently excluded. The adapter pattern is explicitly designed
to accommodate them. A future `live` adapter type could wrap a full audio session behind
the same interface the engine uses today, with the pipeline adapters and live adapters
as parallel paths selectable via config:

```yaml
# config/default.yaml
mode: pipeline   # or: live

# pipeline mode uses individual stt/vad/tts/llm adapters (default)
# live mode uses a single live audio adapter
live:
  provider: openai_realtime   # or: gemini_live
```

Users who want lower latency and are comfortable with the API costs and stability
trade-offs will be able to opt in. The pipeline remains the default until live audio
APIs reach a stability and accessibility level comparable to today's text-model APIs.
