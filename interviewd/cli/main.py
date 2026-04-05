import asyncio
from typing import Optional

import typer

app = typer.Typer(help="Interviewd — voice mock interview agent")

_CONFIG_OPTION = typer.Option("config/default.yaml", help="Path to config YAML")


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


@app.command()
def plan(
    jd: str = typer.Option(..., "--jd", help="Path to job description (.pdf, .txt, .md)"),
    resume: str = typer.Option(..., "--resume", help="Path to resume / CV (.pdf, .txt, .md)"),
    output: str = typer.Option(
        "local/plans/plan.yaml",
        "--output", "-o",
        help="Where to save the generated plan YAML (default: local/plans/plan.yaml)",
    ),
    type: str = typer.Option("technical", help="Interview type: behavioral | technical | hr | system_design"),
    difficulty: str = typer.Option("mid", help="Difficulty: entry | mid | senior | staff"),
    questions: int = typer.Option(5, help="Number of questions to generate"),
    config: str = _CONFIG_OPTION,
) -> None:
    """Generate a tailored interview plan from a job description and resume.

    The plan is saved to --output (default local/plans/plan.yaml, which is
    gitignored). Pass it to an interview session with:

      interviewd interview --plan local/plans/plan.yaml

    Standard pre-made plans ship in config/plans/ and need no JD/resume.
    """
    from interviewd.cli.plan import run_plan

    _VALID_TYPES = ("behavioral", "technical", "hr", "system_design")
    _VALID_DIFFICULTIES = ("entry", "mid", "senior", "staff")

    if type not in _VALID_TYPES:
        typer.echo(f"Invalid type '{type}'. Choose from: {', '.join(_VALID_TYPES)}", err=True)
        raise typer.Exit(1)
    if difficulty not in _VALID_DIFFICULTIES:
        typer.echo(f"Invalid difficulty '{difficulty}'. Choose from: {', '.join(_VALID_DIFFICULTIES)}", err=True)
        raise typer.Exit(1)

    run_plan(
        jd=jd,
        resume=resume,
        output=output,
        config_path=config,
        interview_type=type,
        difficulty=difficulty,
        num_questions=questions,
    )


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


@app.command()
def setup(
    force: bool = typer.Option(False, "--force", "-f", help="Re-configure keys that are already set"),
    start: Optional[bool] = typer.Option(None, "--start/--no-start", help="Start dev server after setup"),
) -> None:
    """Configure API keys and optionally start the dev server. For a fresh clone, run bash setup.sh instead."""
    from interviewd.cli.setup import run_setup
    run_setup(force=force, start=start)


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


# ---------------------------------------------------------------------------
# interview
# ---------------------------------------------------------------------------


@app.command()
def interview(
    type: str = typer.Option("behavioral", help="Interview type: behavioral | technical | hr | system_design"),
    difficulty: str = typer.Option("mid", help="Difficulty: entry | mid | senior | staff"),
    questions: int = typer.Option(5, help="Number of questions"),
    plan_path: Optional[str] = typer.Option(
        None, "--plan",
        help="Path to a plan YAML (from 'interviewd plan' or config/plans/). "
             "When provided, overrides --type/--difficulty/--questions and uses the plan's question list.",
    ),
    config: str = _CONFIG_OPTION,
) -> None:
    """Run a full voice mock interview and save the session.

    To run from a pre-made plan (no JD/resume needed):

      interviewd interview --plan config/plans/swe_technical_senior.yaml

    To run from a personalised AI-generated plan:

      interviewd plan --jd job.pdf --resume resume.pdf
      interviewd interview --plan local/plans/plan.yaml
    """
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

    settings = load_settings(config)

    # --plan path: load plan and derive interview config + questions from it
    if plan_path is not None:
        from interviewd.planner.models import InterviewPlan

        try:
            loaded_plan = InterviewPlan.from_yaml(plan_path)
        except FileNotFoundError:
            typer.echo(f"Plan file not found: {plan_path}", err=True)
            raise typer.Exit(1)

        interview_config = InterviewConfig(
            type=loaded_plan.interview_type,
            difficulty=loaded_plan.difficulty,
            num_questions=loaded_plan.num_questions,
            time_limit_per_question=loaded_plan.time_limit_per_question,
            persona=loaded_plan.persona,
            language=loaded_plan.language,
        )
        planned_questions = loaded_plan.to_questions()
        typer.echo(
            f"Loaded plan: {loaded_plan.interview_type} / {loaded_plan.difficulty} "
            f"({len(planned_questions)} questions)"
        )
    else:
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

        interview_config = InterviewConfig(
            type=type,
            difficulty=difficulty,
            num_questions=questions,
            time_limit_per_question=settings.interview.time_limit_per_question,
            persona=settings.interview.persona,
            language=settings.interview.language,
        )
        planned_questions = None

    async def _run() -> None:
        vad = get_vad_adapter(settings.vad)
        stt = get_stt_adapter(settings.stt)
        tts = get_tts_adapter(settings.tts)
        llm = get_llm_adapter(settings.llm)

        if planned_questions is not None:
            picked = planned_questions
        else:
            bank = QuestionBank(settings.paths.question_bank)
            picked = bank.pick(interview_config)
            if not picked:
                typer.echo(
                    f"No questions found for type='{interview_config.type}' "
                    f"difficulty='{interview_config.difficulty}'.",
                    err=True,
                )
                raise typer.Exit(1)

        typer.echo(
            f"Starting {interview_config.difficulty} {interview_config.type} "
            f"interview ({len(picked)} questions)…"
        )

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
