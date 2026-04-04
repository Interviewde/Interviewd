# ADR 005 — Dual-Path Interview Engine: Pipeline vs. Live

**Status:** Accepted  
**Date:** 2026-04-04  
**Deciders:** Abhishek Paliwal

---

## Context

Two architectural approaches exist for conducting a voice interview:

**Path A — Pipeline mode** (current, Sprint 1)
```
Mic → VAD → STT → LLM → TTS → Speaker
```
Each stage is a discrete adapter. The user speaks, VAD detects silence, STT
transcribes, LLM generates a response, TTS synthesises audio, the speaker plays it.

**Path B — Live mode** (planned, Sprint 3–4)
```
Mic ↔ LiveLLMAdapter (WebSocket) ↔ Speaker
```
A single persistent WebSocket to a real-time voice API (e.g. Gemini Live, OpenAI
Realtime) replaces all four adapters. The provider handles VAD, STT, reasoning, and
TTS internally.

The question is whether to replace pipeline mode with live mode or support both.

---

## Why keep pipeline mode

### Cost

| Mode | Approximate cost per 30-min interview |
|------|--------------------------------------|
| Pipeline (Groq STT + local LLM + Edge TTS) | ~$0.00 (fully free tier / local) |
| Pipeline (Groq STT + GPT-4o + Edge TTS) | ~$0.10–$0.30 |
| Live (Gemini Live / OpenAI Realtime) | ~$0.50–$2.00 |

Live APIs charge per audio minute regardless of silence. For a student running 10
interviews a day, live mode cost is non-trivial. Pipeline mode can be run entirely
for free using Groq's free tier for STT and a local LLM (Ollama, LM Studio).

### Privacy

Pipeline mode with local models (`whisper_local`, Ollama) processes audio entirely
on-device. No audio leaves the machine. This matters for users practising sensitive
topics (salary negotiation, personal background questions) or operating under data
residency constraints.

### Resilience

Pipeline mode degrades gracefully: if TTS fails, the question is shown as text; if
STT fails, the user can type. Live mode is all-or-nothing — a dropped WebSocket ends
the session.

### Existing investment

Sprint 1 built and tested four adapter families (STT, TTS, VAD, LLM) with 98 tests.
Discarding this work in favour of a single live adapter would eliminate the ability to
mix providers (e.g. Groq STT + local LLM + Edge TTS).

---

## Why add live mode

### Latency

Pipeline mode has 3–5 seconds of latency per turn (VAD silence detection + STT API
round-trip + LLM round-trip + TTS synthesis + playback). Live APIs achieve < 500 ms
end-to-end, making the conversation feel natural rather than transactional.

### Naturalness

Live APIs support interruptions — the user can cut off the interviewer mid-sentence,
exactly as in a real interview. Pipeline mode cannot support this without significant
complexity in the VAD layer.

### Quality

Models specifically tuned for real-time voice (Gemini 2.0 Flash Live, GPT-4o Realtime)
produce more contextually appropriate responses than text LLMs asked to generate
"spoken" output.

---

## Decision

**Support both paths. Mode is a per-session configuration choice.**

Neither path is deprecated. Users choose based on their priorities:

| Priority | Recommended mode |
|----------|-----------------|
| Free / offline / private | Pipeline |
| Natural conversation / low latency | Live |
| Debugging / development | Pipeline (deterministic, easy to mock) |
| Demo / production quality | Live |

---

## Implementation

### Configuration

A top-level `mode` field on `InterviewConfig` selects the path:

```yaml
# config/default.yaml
interview:
  mode: pipeline          # pipeline | live
  ...
```

```python
class InterviewConfig(BaseModel):
    mode: Literal["pipeline", "live"] = "pipeline"
    ...
```

The web UI exposes this as a toggle on the setup screen. The CLI defaults to
`pipeline` (preserving all existing behaviour — zero breaking change).

### Engine selection

The interview execution layer reads `config.mode` and dispatches accordingly:

```
mode = "pipeline"  →  InterviewEngine  (VAD + STT + LLM + TTS adapters)
mode = "live"      →  LiveInterviewEngine  (LiveLLMAdapter only)
```

Both engines produce an `InterviewSession` with identical structure. The `Scorer`
and `SessionStore` are unaware of which engine ran.

### LiveLLMAdapter

A new adapter family (`interviewd/adapters/live_llm/`) follows the same
`__init_subclass__(provider=...)` registry pattern as all other adapters:

```
interviewd/adapters/live_llm/
  base.py      — abstract LiveLLMAdapter + typed event models
  registry.py  — get_live_llm_adapter(config)
  # provider implementations added per-sprint:
  # gemini_live.py, openai_realtime.py, ...
```

Provider implementations are drop-in: add one file, zero changes to routes or config
schema.

### Event model

Live sessions emit typed events (Pydantic models with a `type` discriminator):

```
SessionStartedEvent   — connection established
AudioDeltaEvent       — PCM chunk to play to the user
TextDeltaEvent        — partial transcript of AI turn
TurnCompleteEvent     — AI finished speaking
InputCommittedEvent   — provider acknowledged user audio
InterruptedEvent      — user interrupted the AI
ErrorEvent            — unrecoverable error
```

The FastAPI WebSocket handler serialises these events to JSON and forwards them to the
browser. The React frontend pattern-matches on `type`.

---

## What does NOT change

| Component | Pipeline mode | Live mode |
|-----------|--------------|-----------|
| `QuestionBank` | used | used |
| `Scorer` | used (post-session) | used (post-session) |
| `SessionStore` | used | used |
| `InterviewSession` / `Turn` | produced | produced |
| CLI | works | not applicable (CLI stays pipeline-only) |
| STT / TTS / VAD adapters | used | not used |

---

## Consequences

- The pipeline adapter ecosystem (STT, TTS, VAD) remains a first-class feature.
  Contributors can add providers to either path independently.
- Live mode is purely additive — existing tests, CLI behaviour, and pipeline adapters
  are untouched.
- Future providers (Hume AI, ElevenLabs Conversational) are one new file each.
- If a live provider is deprecated or too expensive, users switch `mode: pipeline`
  in one config line.
