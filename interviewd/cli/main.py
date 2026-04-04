import asyncio
from typing import Optional

import typer

app = typer.Typer(help="Interviewd — voice mock interview agent")


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version, PackageNotFoundError
        try:
            ver = version("interviewd")
        except PackageNotFoundError:
            ver = "dev"
        typer.echo(f"interviewd {ver}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass

_CONFIG_OPTION = typer.Option("config/default.yaml", help="Path to config YAML")


# ---------------------------------------------------------------------------
# interview
# ---------------------------------------------------------------------------


@app.command()
def interview(
    type: str = typer.Option("behavioral", help="Interview type: behavioral | technical | hr | system_design"),
    difficulty: str = typer.Option("mid", help="Difficulty: entry | mid | senior | staff"),
    questions: int = typer.Option(5, help="Number of questions"),
    config: str = _CONFIG_OPTION,
) -> None:
    """Run a full voice mock interview and save the session."""
    # Defer heavy imports so `--help` stays instant
    from interviewd.config import InterviewConfig, load_settings
    from interviewd.adapters.llm.registry import get_llm_adapter
    from interviewd.adapters.stt.registry import get_stt_adapter
    from interviewd.adapters.tts.registry import get_tts_adapter
    from interviewd.adapters.vad.registry import get_vad_adapter
    from interviewd.data.question_bank import QuestionBank
    from interviewd.engine.interview import InterviewEngine
    from interviewd.engine.voice_loop import VoiceLoop
    from interviewd.scoring.scorer import Scorer
    from interviewd.store.session_store import SessionStore

    _VALID_TYPES = ("behavioral", "technical", "hr", "system_design")
    _VALID_DIFFICULTIES = ("entry", "mid", "senior", "staff")

    if type not in _VALID_TYPES:
        typer.echo(
            f"Invalid interview type '{type}'. Choose from: {', '.join(_VALID_TYPES)}",
            err=True,
        )
        raise typer.Exit(1)
    if difficulty not in _VALID_DIFFICULTIES:
        typer.echo(
            f"Invalid difficulty '{difficulty}'. Choose from: {', '.join(_VALID_DIFFICULTIES)}",
            err=True,
        )
        raise typer.Exit(1)

    settings = load_settings(config)

    # CLI flags override config-file values
    interview_config = InterviewConfig(
        type=type,
        difficulty=difficulty,
        num_questions=questions,
        time_limit_per_question=settings.interview.time_limit_per_question,
        persona=settings.interview.persona,
        language=settings.interview.language,
    )

    async def _run() -> None:
        vad = get_vad_adapter(settings.vad)
        stt = get_stt_adapter(settings.stt)
        tts = get_tts_adapter(settings.tts)
        llm = get_llm_adapter(settings.llm)

        bank = QuestionBank(settings.paths.question_bank)
        picked = bank.pick(interview_config)
        if not picked:
            typer.echo(
                f"No questions found for type='{type}' difficulty='{difficulty}'.",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo(f"Starting {difficulty} {type} interview ({len(picked)} questions)…")

        voice_loop = VoiceLoop(vad, stt, tts)
        engine = InterviewEngine(voice_loop, llm, interview_config, picked)
        session = await engine.run()

        typer.echo("\nScoring your answers…")
        scorer = Scorer(llm)
        report = await scorer.score(session)

        store = SessionStore(settings.paths.session_store)
        session_id = store.save(session, report)

        typer.echo(f"\n✓ Session saved  →  {session_id}")
        typer.echo(f"  Overall score : {report.average_overall}/10")
        typer.echo(f"  Run 'interviewd report {session_id}' for the full report.")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


@app.command()
def report(
    session_id: str = typer.Argument(..., help="Session ID returned by 'interviewd interview'"),
    config: str = _CONFIG_OPTION,
) -> None:
    """Display the transcript and scores for a saved session."""
    from interviewd.config import load_settings
    from interviewd.store.session_store import SessionStore

    settings = load_settings(config)
    store = SessionStore(settings.paths.session_store)

    try:
        saved = store.load(session_id)
    except KeyError:
        typer.echo(f"Session not found: {session_id}", err=True)
        raise typer.Exit(1)

    session = saved.interview_session
    score_report = saved.score_report
    cfg = session.config

    _hr()
    typer.echo(f" INTERVIEW REPORT  •  {cfg.type} / {cfg.difficulty}")
    typer.echo(f" Session: {session_id[:8]}…  •  {len(session.turns)} question(s)")
    _hr()

    scores_by_qid = {s.question_id: s for s in score_report.scores}

    for i, turn in enumerate(session.turns, start=1):
        typer.echo(f"\nQ{i}: {turn.question.text}\n")
        typer.echo(f"  You: {turn.answer}")
        if turn.follow_up_asked:
            typer.echo(f"\n  Follow-up: {turn.question.follow_up}")
            typer.echo(f"  You: {turn.follow_up_answer}")

        score = scores_by_qid.get(turn.question.id)
        if score:
            typer.echo(
                f"\n  STAR {score.star_score}/10  •  "
                f"Relevance {score.relevance_score}/10  •  "
                f"Clarity {score.clarity_score}/10  •  "
                f"Overall {score.overall}/10"
            )
            typer.echo(f"  Feedback: {score.feedback}")

    _hr()
    typer.echo(" SUMMARY")
    _hr()
    typer.echo(f"\n  Overall  : {score_report.average_overall}/10")
    typer.echo(f"  STAR avg : {score_report.average_star}/10")
    typer.echo(f"  Relevance: {score_report.average_relevance}/10")
    typer.echo(f"  Clarity  : {score_report.average_clarity}/10")
    if score_report.summary:
        typer.echo(f"\n  {score_report.summary}")
    _hr()


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------


@app.command()
def sessions(
    config: str = _CONFIG_OPTION,
) -> None:
    """List all saved interview sessions."""
    from interviewd.config import load_settings
    from interviewd.store.session_store import SessionStore

    settings = load_settings(config)
    store = SessionStore(settings.paths.session_store)
    rows = store.list_sessions()

    if not rows:
        typer.echo("No sessions found.")
        return

    # Header
    typer.echo(f"\n{'ID':<38}  {'TYPE':<12}  {'DIFFICULTY':<10}  {'SCORE':>5}  DATE")
    typer.echo("─" * 80)
    for r in rows:
        score = f"{r['avg_overall']:.1f}" if r["avg_overall"] is not None else "  — "
        date = str(r["created_at"])[:10]
        typer.echo(
            f"{r['id']:<38}  {r['interview_type']:<12}  {r['difficulty']:<10}  {score:>5}  {date}"
        )
    typer.echo()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hr() -> None:
    typer.echo("─" * 60)


if __name__ == "__main__":
    app()
