"""Identity and session operations."""

from flask import session
from flask_login import login_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.repositories.users import UserRepository


class DuplicateIdentity(Exception):  # noqa: N818
    """The username or nickname is already in use."""


def register_user(username: str, nickname: str, password: str) -> User:
    user = User(
        username=username.lower(), nickname=nickname, nickname_key=nickname.lower()
    )
    user.set_password(password)
    try:
        UserRepository(db.session).add(user)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise DuplicateIdentity from exc
    return user


def authenticate(username: str, password: str) -> User | None:
    user = UserRepository(db.session).by_username(username.lower())
    return user if user and user.check_password(password) else None


def start_session(user: User) -> None:
    session.clear()
    login_user(user)
    session.permanent = True
