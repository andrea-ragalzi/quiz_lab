"""Security headers, SQLite foreign keys, and structured logging."""

import json
import logging
import sqlite3

from flask import Flask, Response, request
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry


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


def register(app: Flask) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app.logger.handlers = [handler]

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
