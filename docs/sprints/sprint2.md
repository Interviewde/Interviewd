# Sprint 2 — Apr 5–11, 2026

## Goals
Four features shipped by end of day Apr 11:
1. Setup wizard
2. JD + Resume planner agent
3. Post-session report
4. Gemini Live voice path

---

## Day 1 — Sun Apr 6 — Setup Wizard

**Goal:** `uv run interviewd setup` detects missing keys, links to signup pages, validates keys live, writes `.env`

**Tasks:**
- [ ] `interviewd/cli/setup.py` — wizard command
- [ ] Validate each key by making a cheap test call (e.g. `groq.models.list()`)
- [ ] Write/update `.env` without clobbering existing keys
- [ ] Register `setup` subcommand in `interviewd/cli/main.py`

**Done when:** a user with no `.env` can run `setup` and emerge with working keys

---

## Day 2–3 — Mon–Tue Apr 7–8 — JD + Resume Planner Agent

**Goal:** `interviewd plan --jd job.pdf --resume resume.pdf` outputs a tailored `InterviewConfig` + question list

**Tasks:**
- [ ] `interviewd/planner/` — new module
- [ ] PDF/text ingestion (PyMuPDF or `pypdf`)
- [ ] LLM prompt: extract required skills from JD, score resume against them, output weighted question plan
- [ ] Question plan serializable to YAML/JSON, loadable by the engine
- [ ] CLI flag `--plan plan.yaml` to run a session from a generated plan

**Done when:** plan command produces a question set noticeably different for a SWE JD vs a PM JD

---

## Day 4 — Wed Apr 9 — Post-Session Report

**Goal:** after every session, a Markdown report is saved with transcript + per-question scores

**Tasks:**
- [ ] Extend `interviewd/scoring/scorer.py` to score each answer against the question intent
- [ ] `interviewd/report/` — new module, renders Markdown (and optionally HTML)
- [ ] Add transcript field to `interviewd/store/session_store.py`
- [ ] CLI prints report path at session end
- [ ] Web UI gets a `/sessions/{id}/report` endpoint

**Done when:** `.interviewd/sessions/<id>/report.md` exists after a session with meaningful per-question feedback

---

## Day 5–6 — Thu–Fri Apr 10–11 — Gemini Live Voice Path

**Goal:** `mode: live` in config uses Gemini Live API instead of VAD→STT→LLM→TTS pipeline

**Tasks:**
- [ ] `interviewd/adapters/live/gemini_live.py` — WebSocket connection to Gemini Live API
- [ ] Audio in/out passthrough (browser MediaStream → WS → Gemini → WS → browser)
- [ ] Fill in `LiveLLMConfig.model` default in `config.py` (stub already exists)
- [ ] Web UI: detect `mode: live` and switch to direct audio passthrough instead of pipeline UI
- [ ] Session recording + transcript extraction from Gemini response events (for report compat)

**Done when:** a session runs end-to-end with `mode: live` with noticeably lower latency than pipeline mode

---

## Day 7 — Sat Apr 12 — Buffer / Integration

**Tasks:**
- [ ] Wire all four features together (plan → session → report)
- [ ] CI tests for setup wizard (mock key validation) and planner (mock LLM)
- [ ] Update `README.md` and `.env.example`
- [ ] Cut PR, merge to main

---

## Open Risks

| Risk | Mitigation |
|---|---|
| Gemini Live WebSocket API has breaking changes / limited docs | Timebox to 1.5 days; stub if blocked |
| PDF parsing quality varies | Accept plain text `.txt` as fallback for resume/JD |
| Scorer quality depends heavily on prompt | Ship v1 with a simple rubric, iterate |

---

## Status

| Feature | Status |
|---|---|
| Setup wizard | Not started |
| JD + Resume planner | Not started |
| Post-session report | Not started |
| Gemini Live voice path | Not started |
