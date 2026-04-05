"""interviewd setup — configure API keys and optionally start the dev server.

For first-time setup from a fresh clone, run `bash setup.sh` at the repo
root instead — it installs uv, Python, Node.js, and all dependencies before
calling this wizard.
"""
import os
import sys
from pathlib import Path

# Ensure box-drawing / emoji characters render correctly on Windows terminals
# that default to cp1252.  No-op on macOS/Linux where utf-8 is the default.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

import typer
from dotenv import dotenv_values, set_key

ENV_FILE = Path(".env")
FRONTEND_DIR = Path("frontend")

_KEY_DEFS = [
    {
        "name": "GROQ_API_KEY",
        "label": "Groq API key",
        "required": True,
        "signup": "https://console.groq.com",
        "desc": "STT (Whisper) and optional LLM — free tier available",
    },
    {
        "name": "GOOGLE_API_KEY",
        "label": "Google AI Studio API key",
        "required": False,
        "signup": "https://aistudio.google.com/app/apikey",
        "desc": "LLM (Gemini) — default model, free tier available",
    },
    {
        "name": "OPENAI_API_KEY",
        "label": "OpenAI API key",
        "required": False,
        "signup": "https://platform.openai.com/api-keys",
        "desc": "Optional — only needed if using openai/* models in config",
    },
    {
        "name": "ANTHROPIC_API_KEY",
        "label": "Anthropic API key",
        "required": False,
        "signup": "https://console.anthropic.com",
        "desc": "Optional — only needed if using anthropic/* models in config",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hr(char: str = "─", width: int = 50) -> None:
    typer.echo(char * width)


def _ok(msg: str) -> None:
    typer.echo(f"  ✓  {msg}")


def _info(msg: str) -> None:
    typer.echo(f"     {msg}")


def _run(cmd: list[str], cwd: Path | None = None) -> bool:
    import subprocess
    return subprocess.run(cmd, cwd=cwd).returncode == 0


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------


def _validate_key(name: str, key: str) -> tuple[bool, str]:
    """Make a cheap metadata call to verify the key is accepted by the provider."""
    try:
        if name == "GROQ_API_KEY":
            from groq import Groq
            Groq(api_key=key).models.list()

        elif name == "GOOGLE_API_KEY":
            import google.generativeai as genai
            genai.configure(api_key=key)
            list(genai.list_models())

        elif name == "OPENAI_API_KEY":
            try:
                import openai
            except ImportError:
                return True, "saved (openai package not installed — install when needed)"
            openai.OpenAI(api_key=key).models.list()

        elif name == "ANTHROPIC_API_KEY":
            try:
                import anthropic
            except ImportError:
                return True, "saved (anthropic package not installed — install when needed)"
            anthropic.Anthropic(api_key=key).models.list()

        return True, "validated"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_setup(force: bool = False, start: bool | None = None) -> None:
    """Configure API keys, write to .env, and optionally start the dev server."""
    typer.echo()
    _hr("═")
    typer.echo("  Interviewd — API Key Configuration")
    _hr("═")

    env_file_vals = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    any_written = False

    for kd in _KEY_DEFS:
        name: str = kd["name"]  # type: ignore[assignment]
        label: str = kd["label"]  # type: ignore[assignment]
        required: bool = kd["required"]  # type: ignore[assignment]
        signup: str = kd["signup"]  # type: ignore[assignment]
        desc: str = kd["desc"]  # type: ignore[assignment]

        existing = env_file_vals.get(name) or os.environ.get(name, "")

        if existing and not force:
            _ok(f"{name}  already set — skipping")
            continue

        tag = "required" if required else "optional"
        typer.echo(f"\n  {label}  [{tag}]")
        _info(desc)
        _info(f"Sign up : {signup}")

        if not required:
            if not typer.confirm("  Configure this key?", default=False):
                _info(f"Skipping {name}")
                continue

        while True:
            value = typer.prompt(f"  Paste your {label}", hide_input=True).strip()
            if not value:
                _info("Value cannot be empty — try again.")
                continue

            typer.echo("     Validating…", nl=False)
            ok, msg = _validate_key(name, value)
            if ok:
                typer.echo(" ✓")
                set_key(str(ENV_FILE), name, value)
                any_written = True
                break
            else:
                typer.echo(f" ✗\n     {msg}")
                if not typer.confirm("  Try a different key?", default=True):
                    break

    typer.echo()
    _hr("═")
    if any_written:
        _ok(f"Keys written to {ENV_FILE.resolve()}")
    _ok("Configuration complete")
    _hr("═")
    typer.echo()

    # Optionally start the dev server
    if start is None:
        start = typer.confirm("  Start the dev server now?", default=True)

    if start:
        typer.echo()
        typer.echo("  Starting Interviewd  →  API :8000  •  UI :5173")
        typer.echo("  Press Ctrl+C to stop.\n")
        _run(["npm", "run", "dev:all"], cwd=FRONTEND_DIR)
    else:
        typer.echo("  To start later:\n")
        typer.echo("      cd frontend && npm run dev:all\n")
