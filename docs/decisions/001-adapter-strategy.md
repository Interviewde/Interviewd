# ADR 001 — Adapter Strategy for STT, TTS, and LLM Providers

## Status
Accepted

## Context

Interviewd is designed as a plug-and-play framework. Users should be able to
switch providers (e.g. swap Groq Whisper for Deepgram, or Gemini for Mistral)
without writing or modifying any Python code — only by editing `config/default.yaml`.

We considered three approaches for provider configuration:

1. **Literal config values** — restrict provider fields to a fixed set of known strings
   using Pydantic `Literal`. Simple, but requires modifying `config.py` every time a
   new provider is added. Puts the burden on core maintainers.

2. **Manual registry** — contributors create an adapter file and also manually add an
   entry to a central registry dict. Works, but the two-step process is error-prone and
   the registry becomes a merge conflict hotspot.

3. **Auto-registration via `__init_subclass__` + autodiscovery** — each adapter
   registers itself the moment its class is defined. A discovery function imports all
   modules in the adapters directory at startup, triggering registration automatically.
   Contributors only create one file; no other file needs touching.

## Decision

### Core rule

> Use `Literal` for closed sets we control. Use `str` for genuinely open-ended plugin points.

### STT and TTS — `Literal` config + auto-registration

Built-in STT providers: `groq`, `whisper_local`
Built-in TTS providers: `edge_tts`, `piper`

These are a closed set we ship and maintain. `Literal` is used in `config.py` so:
- Users get a validation error at startup for typos (e.g. `"edg_tts"`) rather than
  a confusing failure deep in the audio pipeline.
- When a contributor adds a new built-in provider, updating the `Literal` is a
  one-line diff that makes the addition explicit and reviewable in the PR.

Under the hood, adapters use `__init_subclass__` + `_autodiscover()` so contributors
still only create one file — the `Literal` update in `config.py` is the only other
required change.

A generic HTTP-based adapter driven purely by config was considered but rejected.
Each STT and TTS API has fundamentally different audio formats, streaming behaviour,
and authentication — encoding all of that in YAML would be harder to use and maintain
than a simple Python class.

### LLM — `str` config + LiteLLM as the default adapter

LiteLLM is a library that wraps 100+ LLM providers under a single unified interface.
Rather than shipping individual adapters for each LLM provider, we ship one LiteLLM
adapter. Users unlock any supported provider purely via config:

```yaml
llm:
  provider: litellm
  model: gemini/gemini-1.5-flash   # switch to any provider by changing this line
```

Because the set of supported LLM providers is effectively unlimited via LiteLLM,
`llm.provider` is a plain `str` — not `Literal`. Validation happens at adapter
lookup time with a clear error message listing available providers.

Full model list: https://docs.litellm.ai/docs/providers

### Authentication

LiteLLM reads the standard environment variables each provider expects — keys come
directly from the provider, not from LiteLLM. There is no LiteLLM account or payment
required.

| Provider | Env var | Where to get the key |
|---|---|---|
| Gemini | `GEMINI_API_KEY` | Google AI Studio / GCP |
| Groq | `GROQ_API_KEY` | console.groq.com |
| OpenAI | `OPENAI_API_KEY` | platform.openai.com |
| Mistral | `MISTRAL_API_KEY` | console.mistral.ai |
| Cerebras | `CEREBRAS_API_KEY` | cloud.cerebras.ai |

For GCP users, Application Default Credentials (ADC) are also supported — run
`gcloud auth application-default login` and LiteLLM picks it up automatically
with no API key needed.

## Consequences

- End users interact only with `config/default.yaml` — no code changes for common cases.
- Contributors adding new STT/TTS providers create one adapter file and update one
  `Literal` in `config.py` — both changes land in the same PR.
- LLM provider coverage is effectively unlimited via LiteLLM without any adapter code.
- `litellm` is added as a dependency in `pyproject.toml`.
- STT/TTS provider fields use `Literal` for early validation; LLM provider uses `str`.
