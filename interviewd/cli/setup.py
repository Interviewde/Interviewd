"""interviewd setup — full onboarding wizard after cloning the repo."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

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


def _fail(msg: str) -> None:
    typer.echo(f"  ✗  {msg}", err=True)


def _info(msg: str) -> None:
    typer.echo(f"     {msg}")


def _run(cmd: list[str], cwd: Path | None = None) -> bool:
    """Run a command, stream output, return True on success."""
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def _step_prereqs() -> bool:
    typer.echo("\n  [1/4] Checking prerequisites")
    _hr()
    ok = True

    # Python version
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) >= (3, 11):
        _ok(f"Python {major}.{minor}")
    else:
        _fail(f"Python {major}.{minor} — need 3.11+")
        ok = False

    # uv
    if shutil.which("uv"):
        _ok("uv")
    else:
        _fail("uv not found — install from https://docs.astral.sh/uv/")
        ok = False

    # node + npm
    if shutil.which("node"):
        _ok("node")
    else:
        _fail("node not found — install from https://nodejs.org")
        ok = False

    if shutil.which("npm"):
        _ok("npm")
    else:
        _fail("npm not found — install from https://nodejs.org")
        ok = False

    return ok


def _step_python_deps() -> bool:
    typer.echo("\n  [2/4] Installing Python dependencies")
    _hr()
    _info("uv sync --extra web  (this may take a moment on first run)")
    if _run(["uv", "sync", "--extra", "web"]):
        _ok("Python deps ready")
        return True
    _fail("uv sync failed — check output above")
    return False


def _step_frontend_deps() -> bool:
    typer.echo("\n  [3/4] Installing frontend dependencies")
    _hr()
    if not FRONTEND_DIR.exists():
        _fail(f"{FRONTEND_DIR}/ not found")
        return False
    _info("npm install")
    if _run(["npm", "install"], cwd=FRONTEND_DIR):
        _ok("Frontend deps ready")
        return True
    _fail("npm install failed — check output above")
    return False


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


def _step_api_keys(force: bool = False) -> None:
    typer.echo("\n  [4/4] Configuring API keys")
    _hr()

    env_file_vals = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

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
                break
            else:
                typer.echo(f" ✗\n  {msg}")
                if not typer.confirm("  Try a different key?", default=True):
                    break

    typer.echo()
    _ok(f"Keys written to {ENV_FILE.resolve()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_setup(force: bool = False, start: bool | None = None) -> None:
    """Full setup: prereqs → deps → API keys → optionally start the server."""
    typer.echo()
    _hr("═")
    typer.echo("  Interviewd Setup")
    _hr("═")

    # Step 1 — prereqs (abort if something critical is missing)
    if not _step_prereqs():
        typer.echo("\n  Fix the issues above, then re-run 'interviewd setup'.")
        raise typer.Exit(1)

    # Step 2 — Python deps (soft abort)
    if not _step_python_deps():
        if not typer.confirm("\n  Python deps failed. Continue anyway?", default=False):
            raise typer.Exit(1)

    # Step 3 — frontend deps (soft abort)
    if not _step_frontend_deps():
        if not typer.confirm("\n  Frontend deps failed. Continue anyway?", default=False):
            raise typer.Exit(1)

    # Step 4 — API keys
    _step_api_keys(force=force)

    # Done
    typer.echo()
    _hr("═")
    _ok("Setup complete!")
    _hr("═")
    typer.echo()

    # Optionally start the dev server
    if start is None:
        start = typer.confirm("  Start the dev server now?", default=True)

    if start:
        typer.echo()
        typer.echo("  Starting Interviewd  →  API on :8000  •  UI on :5173")
        typer.echo("  Press Ctrl+C to stop.\n")
        _run(["npm", "run", "dev:all"], cwd=FRONTEND_DIR)
    else:
        typer.echo("  To start later, run:\n")
        typer.echo("      cd frontend && npm run dev:all\n")
