"""QuizLab application factory."""

import json
import logging
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import click
from flask import Flask, Response, render_template, request
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry
from werkzeug.exceptions import HTTPException

from app.config import configuration
from app.extensions import csrf, db, login_manager


@event.listens_for(Engine, "connect")
def configure_sqlite(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    """Enforce foreign keys on every new SQLite connection."""
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


class JsonFormatter(logging.Formatter):
    """Serialize log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        # Tracebacks stay in server logs; request bodies are never serialized.
        # ``exc_info`` may be ``(None, None, None)`` when no exception is active.
        traceback = exception_type = None
        exc_info = record.exc_info
        if exc_info is not None and exc_info[0] is not None:
            traceback = self.formatException(exc_info)
            exception_type = exc_info[0].__name__
        return json.dumps(
            {
                "level": record.levelname,
                "event": record.getMessage(),
                "traceback": traceback,
                "exception_type": exception_type,
            }
        )


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
    """Create and configure a QuizLab application instance."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(configuration(app.instance_path))
    if config:
        app.config.update(config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set in the environment.")
    if app.testing:
        app.config["SESSION_COOKIE_SECURE"] = False
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app.logger.handlers = [handler]
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    # Flask-Login is untyped and initialises ``login_view`` to ``None``, so the
    # inferred attribute type rejects the documented string assignment.
    login_manager.login_view = "auth.login"  # pyright: ignore[reportAttributeAccessIssue]
    login_manager.login_message = "Accedi per continuare."
    from app.presentation import SAFE_MESSAGES, italian

    app.jinja_env.filters["italian"] = italian

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id)) if user_id.isdecimal() else None

    from app.auth.routes import bp as auth
    from app.leaderboard.routes import bp as leaderboard
    from app.main.routes import bp as main
    from app.quiz.routes import bp as quiz
    from app.weather.routes import bp as weather
    from app.weather.service import WeatherService

    app.extensions["weather"] = WeatherService()
    for blueprint in (main, auth, quiz, leaderboard, weather):
        app.register_blueprint(blueprint)

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException) -> tuple[str, int]:
        description = error.description or ""
        title = italian(error.name)
        message = italian(description)
        if title == error.name:
            title = "Operazione non disponibile"
        if message == description and message not in SAFE_MESSAGES:
            message = "La richiesta non è valida. Ricarica la pagina e riprova."
        # Flask returns code-less proxy exceptions unchanged, so ``code`` is set.
        code = error.code or 500
        return render_template(
            "error.html", code=code, title=title, message=message
        ), code

    @app.errorhandler(500)
    def server_error(_error: Exception) -> tuple[str, int]:
        db.session.rollback()
        return render_template(
            "error.html",
            code=500,
            title="Si è verificato un problema",
            message="Riprova tra qualche istante.",
        ), 500

    @app.after_request
    def security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.cli.command("init-db")
    def init_db() -> None:
        """Create database tables without removing existing data."""
        db.create_all()
        click.echo("Database initialized.")

    @app.cli.command("seed-questions")
    def seed() -> None:
        """Validate and import the configured question bank idempotently."""
        from app.questions import import_static_questions

        count = import_static_questions()
        click.echo(f"Question bank ready: {count} questions.")

    @app.cli.command("validate-questions")
    def validate() -> None:
        """Validate the bank without changing the database."""
        from app.questions import load_static_questions

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
        from app.questions import STATIC_IT_PATH, import_static_questions

        try:
            count = import_static_questions(path or STATIC_IT_PATH)
        except (ValueError, OSError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(f"Imported {count} static questions; existing progress preserved.")

    return app
