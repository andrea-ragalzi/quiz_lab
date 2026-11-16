"""Round and answer persistence operations."""

from flask_sqlalchemy.session import Session as FlaskSession
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, scoped_session

from app.models import AnswerSnapshot, QuizAnswer, QuizRound


class RoundRepository:
    def __init__(self, session: Session | scoped_session[FlaskSession]):
        self.session = session

    def active_for(self, user_id: int) -> QuizRound | None:
        return self.session.scalar(
            select(QuizRound).where(
                QuizRound.user_id == user_id, QuizRound.completed_at.is_(None)
            )
        )

    def owned(self, round_id: str, user_id: int) -> QuizRound | None:
        return self.session.scalar(
            select(QuizRound).where(
                QuizRound.id == round_id, QuizRound.user_id == user_id
            )
        )

    def pending_answer(self, round_id: str) -> QuizAnswer | None:
        return self.session.scalar(
            select(QuizAnswer)
            .where(
                QuizAnswer.round_id == round_id, QuizAnswer.selected_option.is_(None)
            )
            .order_by(QuizAnswer.position)
        )

    def claim_answer(self, answer_id: int, option: int, points: int) -> bool:
        result = self.session.execute(
            update(QuizAnswer)
            .where(QuizAnswer.id == answer_id, QuizAnswer.selected_option.is_(None))
            .values(selected_option=option, awarded_points=points)
        )
        if not isinstance(result, CursorResult):
            raise TypeError("UPDATE did not return a cursor result.")
        return result.rowcount == 1

    def create(self, user_id: int, snapshots: list[AnswerSnapshot]) -> QuizRound:
        round_ = QuizRound(user_id=user_id)
        self.session.add(round_)
        self.session.flush()
        for position, snapshot in enumerate(snapshots):
            self.session.add(
                QuizAnswer(round_id=round_.id, position=position, snapshot=snapshot)
            )
        return round_
