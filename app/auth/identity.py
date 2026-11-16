"""Typed access to the user of the current request."""

from flask_login import current_user
from werkzeug.exceptions import Unauthorized

from app.models import User


def authenticated_user() -> User:
    """Return the signed-in user in views protected by ``login_required``.

    Flask-Login's ``current_user`` proxy is untyped, so attribute access on it is
    unchecked. Resolving the proxy once and narrowing it keeps callers typed and
    turns an unexpected anonymous user into a 401 instead of an ``AttributeError``.
    """
    user = current_user._get_current_object()  # documented LocalProxy API
    if not isinstance(user, User):
        raise Unauthorized()
    return user
