"""User persistence operations."""

from flask_sqlalchemy.session import Session as FlaskSession
from sqlalchemy import select, update
from sqlalchemy.orm import Session, scoped_session

from app.models import User


class UserRepository:
    def __init__(self, session: Session | scoped_session[FlaskSession]):
        self.session = session

    def get(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def by_username(self, name: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == name))

    def add(self, user: User) -> None:
        self.session.add(user)

    def add_points(self, user_id: int, points: int) -> None:
        self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(total_score=User.total_score + points)
        )

    def ranking_query(self):
        return select(User).order_by(
            User.total_score.desc(), User.nickname_key, User.id
        )
