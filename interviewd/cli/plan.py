"""Plan command — generate a tailored InterviewPlan from a JD and resume."""

import asyncio
from pathlib import Path


def run_plan(
    jd: str,
    resume: str,
    output: str,
    config_path: str,
    interview_type: str,
    difficulty: str,
    num_questions: int,
) -> None:
    asyncio.run(
        _run(jd, resume, output, config_path, interview_type, difficulty, num_questions)
    )


async def _run(
    jd: str,
    resume: str,
    output: str,
    config_path: str,
    interview_type: str,
    difficulty: str,
    num_questions: int,
) -> None:
    import yaml
    import typer

    from interviewd.adapters.llm.registry import get_llm_adapter
    from interviewd.config import load_settings
    from interviewd.planner.agent import PlannerAgent
    from interviewd.planner.ingestion import extract_text

    settings = load_settings(config_path)
    llm = get_llm_adapter(settings.llm)

    typer.echo(f"Reading job description: {jd}")
    jd_text = extract_text(jd)

    typer.echo(f"Reading resume: {resume}")
    resume_text = extract_text(resume)

    typer.echo("Analysing with LLM (step 1/2: skill analysis)…")
    agent = PlannerAgent(llm)

    plan = await agent.run(
        jd_text=jd_text,
        resume_text=resume_text,
        interview_type=interview_type,
        difficulty=difficulty,
        num_questions=num_questions,
        jd_source=jd,
        resume_source=resume,
    )

    typer.echo("Generating question plan (step 2/2)… done.")

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        yaml.dump(
            plan.model_dump(),
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    gap_skills = [g.skill for g in plan.skills_analysis.skill_gaps]
    typer.echo(f"\n✓ Plan saved  →  {output}")
    typer.echo(f"  Type / difficulty : {plan.interview_type} / {plan.difficulty}")
    typer.echo(f"  Questions         : {len(plan.questions)}")
    if gap_skills:
        typer.echo(f"  Focus areas       : {', '.join(gap_skills)}")
    typer.echo(f"\n  {plan.skills_analysis.summary}")
    typer.echo(f"\nRun your interview:\n  interviewd interview --plan {output}")
