"""Environment configuration, with secure production defaults."""

import os
from datetime import timedelta
from pathlib import Path
from typing import Any


def configuration(instance_path: str) -> dict[str, Any]:
    """Build Flask settings from the environment."""
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": os.environ.get(
            "DATABASE_URL",
            f"sqlite:///{Path(instance_path) / 'quizlab.sqlite'}",
        ),
        "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"timeout": 15}},
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": os.environ.get("COOKIE_SECURE", "1") != "0",
        "REMEMBER_COOKIE_HTTPONLY": True,
        "REMEMBER_COOKIE_SECURE": True,
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
        "MAX_CONTENT_LENGTH": 16 * 1024,
        "DEBUG": False,
    }
