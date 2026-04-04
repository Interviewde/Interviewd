# ADR 003 — LiteLLM as the Default LLM Adapter Despite the March 2026 Supply Chain Incident

## Status
Accepted

## Context

### The incident

In March 2026, a malicious pull request was merged into the LiteLLM repository and
published to PyPI. The injected code exfiltrated API keys from running processes to an
external server. The package was yanked from PyPI within hours of discovery, a clean
release was issued, and a post-mortem was published by the LiteLLM maintainers.

This was a supply chain attack — a compromised human reviewer, not a vulnerability in
LiteLLM's own code. The attacker submitted a PR that appeared legitimate and was merged
before the malicious payload was spotted.

### Why we still depend on LiteLLM

We considered three responses:

1. **Drop LiteLLM, ship individual adapters per provider** — Eliminates the dependency
   but requires writing and maintaining dozens of adapters to match LiteLLM's coverage.
   The operational cost is high and shifts maintenance burden onto contributors
   indefinitely.

2. **Pin to a known-good version and freeze** — Low effort, but leaves users unable to
   pick up legitimate upstream improvements, bug fixes, or new provider support.

3. **Keep LiteLLM with a pinned lower-bound past the incident and recommend mitigations**
   — Balances coverage, maintenance, and security. **This is what we do.**

The incident, while serious, was an isolated human failure in the review process — not
a persistent vulnerability in LiteLLM's architecture. It was detected quickly, handled
transparently, and the LiteLLM maintainers have since tightened their contributor
verification and release signing processes. The risk profile of LiteLLM is now
comparable to any other actively maintained open-source dependency of similar size.

Removing LiteLLM entirely would deprive users of one of the most practically useful
features of Interviewd — the ability to switch between 100+ LLM providers by editing
one line of YAML — in response to a one-time incident that has been fully remediated.

## Decision

LiteLLM remains the default and recommended LLM adapter. We require a version
constraint in `pyproject.toml` that excludes the affected releases:

```
litellm>=1.35.26  # excludes the yanked 1.35.25 release (March 2026 supply chain incident)
```

This constraint is the primary code-level guardrail. The mitigations below are
recommended practice for all users.

## Why a repeat is unlikely

- **The vector was a human reviewer, not an automated pipeline.** The attack relied on
  deceiving a maintainer, not exploiting a code path. It is not the kind of bug that
  silently reappears.
- **PyPI yanks are fast and effective.** The malicious release was unavailable to most
  users before they could install it. Users who had already installed it were notified
  via the public disclosure within the same day.
- **LiteLLM is now under increased scrutiny.** High-profile supply chain incidents
  reliably attract security researchers, auditors, and automated tooling. The project
  now has more eyes than it did before the incident.
- **Our adapter is a thin wrapper.** LiteLLM's surface area inside Interviewd is
  limited to `acompletion()` calls. It does not touch the filesystem, spawn processes,
  or handle authentication beyond reading standard environment variables that the user
  has already set.

## Mitigations for users

These practices apply to Interviewd specifically and to any Python project with
third-party dependencies.

### 1. Pin your full dependency tree

Use `uv lock` (already the default for Interviewd contributors) or `pip-compile` to
generate a lockfile with exact hashes for every package in the dependency tree. A
lockfile means a compromised newer release cannot be silently pulled in during `pip
install`.

```bash
uv lock          # generates uv.lock with SHA-256 hashes
uv sync          # installs exactly what the lockfile specifies
```

Check your lockfile into version control. Review diffs to `uv.lock` before merging
dependency upgrades, the same way you would review any other code change.

### 2. Enable hash-checked installs

If you install from `requirements.txt` rather than a lockfile, use `pip install
--require-hashes`. This causes pip to reject any package whose downloaded hash does not
match a pre-recorded value.

```bash
pip-compile --generate-hashes requirements.in > requirements.txt
pip install --require-hashes -r requirements.txt
```

### 3. Use a private package mirror or audit proxy

Tools like [Artifactory](https://jfrog.com/artifactory/),
[Nexus](https://www.sonatype.com/products/nexus-repository), or
[pypi-mirror](https://github.com/kwikiel/pypi-mirror) let you proxy PyPI through a
controlled cache. Your team can vet new releases before they are available to
developers and CI, and can pull yanked packages out of rotation independently of PyPI.

### 4. Isolate API keys from the process environment

LiteLLM reads API keys from environment variables. Follow least-privilege: set only
the keys needed for the providers you actually use, and scope them as narrowly as the
provider allows (e.g. read-only keys where available, project-scoped keys rather than
org-wide keys).

Do not export API keys into a global shell profile where every process inherits them.
Prefer passing them via `.env` files loaded only for the specific process:

```bash
# .env  (gitignored)
GEMINI_API_KEY=...

# launch
uv run --env-file .env python -m interviewd
```

### 5. Monitor your dependencies with automated tooling

Subscribe to vulnerability alerts for your dependency tree:

- **GitHub Dependabot** — alerts and auto-PRs for known CVEs; free for public and
  private repos.
- **`pip-audit`** — runs locally or in CI against the OSV and PyPI Advisory databases:
  ```bash
  uv run pip-audit
  ```
- **OSV-Scanner** — Google's scanner, covers transitive dependencies across lockfiles.

Add one of these to your CI pipeline so a newly disclosed vulnerability in any
transitive dependency surfaces before it reaches production.

### 6. Escape hatch: swap out LiteLLM without forking

If your organisation's security policy prohibits LiteLLM entirely, Interviewd's
adapter pattern makes it straightforward to replace. Create a file in
`interviewd/adapters/llm/` that subclasses `LLMAdapter`:

```python
class MyDirectAdapter(LLMAdapter, provider="my_provider"):
    async def complete(self, messages, stream=True) -> str: ...
    async def stream(self, messages) -> AsyncIterator[str]: ...
```

Set `llm.provider: my_provider` in `config/default.yaml`. LiteLLM is never imported.
No other files need changing. See ADR 001 for the full registration design.

## Consequences

- `litellm>=1.35.26` is the version constraint in `pyproject.toml`.
- The default user experience (100+ providers via config) is preserved.
- Users who require tighter supply-chain controls have a documented escape hatch and
  a set of concrete mitigations to follow.
- This ADR should be revisited if a second supply chain incident occurs in LiteLLM, or
  if an equivalent library with a stronger security track record becomes available.
