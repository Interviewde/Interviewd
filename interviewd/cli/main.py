import typer

app = typer.Typer(help="Interviewd — voice mock interview agent")


@app.command()
def interview(
    type: str = typer.Option("behavioral", help="Interview type: behavioral | technical | hr | system_design"),
    difficulty: str = typer.Option("mid", help="Difficulty: entry | mid | senior | staff"),
    questions: int = typer.Option(5, help="Number of questions"),
    config: str = typer.Option("config/default.yaml", help="Path to config file"),
):
    """Start a mock interview session."""
    typer.echo(f"Starting {difficulty} {type} interview with {questions} questions...")
    # Engine integration added in Sprint 2


if __name__ == "__main__":
    app()
