"""Localized HTTP and server error handlers."""

from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

from app.core.extensions import db
from app.web.presentation import SAFE_MESSAGES, italian


def register(app: Flask) -> None:
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
