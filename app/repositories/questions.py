"""Question catalog persistence operations."""

from flask_sqlalchemy.session import Session as FlaskSession
from sqlalchemy import func, select
from sqlalchemy.orm import Session, scoped_session

from app.domain import CATEGORY_LABELS
from app.models import Question, QuestionSnapshot


class QuestionRepository:
    def __init__(self, session: Session | scoped_session[FlaskSession]):
        self.session = session

    def catalog(self, category: str | None) -> dict[str, QuestionSnapshot]:
        query = select(Question)
        if category is not None:
            query = query.where(Question.category == category)
        else:
            query = query.where(Question.category.in_(CATEGORY_LABELS))
        return {
            question.id: question.snapshot() for question in self.session.scalars(query)
        }

    def counts_by_category(self) -> dict[str, int]:
        return dict(
            self.session.execute(
                select(Question.category, func.count(Question.id))
                .where(Question.category.in_(CATEGORY_LABELS))
                .group_by(Question.category)
            ).all()
        )

    def upsert_many(self, snapshots: list[QuestionSnapshot]) -> None:
        for snapshot in snapshots:
            self.session.merge(Question(**snapshot))
