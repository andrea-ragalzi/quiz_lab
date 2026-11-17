"""QuizLab application factory."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask

from app.core import cli, security
from app.core.config import configuration
from app.core.extensions import csrf, db, login_manager
from app.web import errors


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
    security.register(app)
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    # Flask-Login is untyped and initialises ``login_view`` to ``None``, so the
    # inferred attribute type rejects the documented string assignment.
    login_manager.login_view = "auth.login"  # pyright: ignore[reportAttributeAccessIssue]
    login_manager.login_message = "Accedi per continuare."
    from app.web.presentation import italian, question_layout

    app.jinja_env.filters["italian"] = italian
    app.jinja_env.filters["question_layout"] = question_layout

    from app.domain.models import User
    from app.repositories.users import UserRepository

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return (
            UserRepository(db.session).get(int(user_id))
            if user_id.isdecimal()
            else None
        )

    from app.routers.auth import bp as auth
    from app.routers.leaderboard import bp as leaderboard
    from app.routers.main import bp as main
    from app.routers.quiz import bp as quiz
    from app.routers.weather import bp as weather
    from app.services.weather import WeatherService

    app.extensions["weather"] = WeatherService()
    for blueprint in (main, auth, quiz, leaderboard, weather):
        app.register_blueprint(blueprint)

    cli.register(app)
    errors.register(app)
    return app
