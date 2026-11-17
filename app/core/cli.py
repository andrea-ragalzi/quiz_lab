"""Database and question-bank commands."""

from pathlib import Path

import click
from flask import Flask

from app.core.extensions import db


def register(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db() -> None:
        """Create database tables without removing existing data."""
        db.create_all()
        click.echo("Database initialized.")

    @app.cli.command("seed-questions")
    def seed() -> None:
        """Validate and import the configured question bank idempotently."""
        from app.services.questions import import_static_questions

        count = import_static_questions()
        click.echo(f"Question bank ready: {count} questions.")

    @app.cli.command("validate-questions")
    def validate() -> None:
        """Validate the bank without changing the database."""
        from app.services.questions import load_static_questions

        questions = load_static_questions()
        click.echo(f"Validated {len(questions)} questions.")

    @app.cli.command("import-static-questions")
    @click.argument(
        "path",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        required=False,
    )
    def import_static(path: Path | None) -> None:
        """Import the Italian static archive without resetting existing player data."""
        from app.services.questions import STATIC_IT_PATH, import_static_questions

        try:
            count = import_static_questions(path or STATIC_IT_PATH)
        except (ValueError, OSError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(f"Imported {count} static questions; existing progress preserved.")
