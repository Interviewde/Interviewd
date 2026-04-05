"""interviewd setup — interactive wizard to configure API keys in .env."""
import os
from pathlib import Path

import typer
from dotenv import dotenv_values, set_key

ENV_FILE = Path(".env")

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
        "required": True,
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


def _validate(name: str, key: str) -> tuple[bool, str]:
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


def run_setup(force: bool = False) -> None:
    """Prompt for missing API keys, validate them live, and write to .env."""
    env_file_vals = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

    typer.echo("\n  Interviewd Setup Wizard")
    typer.echo("─" * 44)
    typer.echo("  Validates API keys live and writes them to .env\n")

    any_written = False

    for kd in _KEY_DEFS:
        name: str = kd["name"]  # type: ignore[assignment]
        label: str = kd["label"]  # type: ignore[assignment]
        required: bool = kd["required"]  # type: ignore[assignment]
        signup: str = kd["signup"]  # type: ignore[assignment]
        desc: str = kd["desc"]  # type: ignore[assignment]

        existing = env_file_vals.get(name) or os.environ.get(name, "")

        if existing and not force:
            typer.echo(f"  ✓ {name}  already set — skipping")
            continue

        tag = "required" if required else "optional"
        typer.echo(f"\n  {label}  [{tag}]")
        typer.echo(f"  {desc}")
        typer.echo(f"  Sign up : {signup}")

        if not required:
            if not typer.confirm("  Configure this key?", default=False):
                typer.echo(f"  Skipping {name}")
                continue

        while True:
            value = typer.prompt(f"  Paste your {label}", hide_input=True).strip()
            if not value:
                typer.echo("  Value cannot be empty — try again.")
                continue

            typer.echo("  Validating…", nl=False)
            ok, msg = _validate(name, value)
            if ok:
                typer.echo(" ✓")
                set_key(str(ENV_FILE), name, value)
                any_written = True
                break
            else:
                typer.echo(f" ✗\n  {msg}")
                if not typer.confirm("  Try a different key?", default=True):
                    break

    typer.echo("\n" + "─" * 44)
    if any_written:
        typer.echo(f"  Keys written to {ENV_FILE.resolve()}")
    typer.echo("  Run 'interviewd interview' to start a session.\n")
