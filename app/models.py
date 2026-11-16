"""Persistence entities; scoring and HTTP concerns live outside these models."""

import uuid
from datetime import UTC, datetime
from typing import Any, NotRequired, TypedDict

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.domain import DIFFICULTIES, OPTION_COUNT, ROUND_LENGTH
from app.extensions import Model, db


class QuestionSnapshot(TypedDict):
    """Question fields copied into a round so later bank edits cannot alter it."""

    id: str
    category: str
    difficulty: str
    text: str
    options: list[str]
    correct_index: int
    explanation: str


class AnswerSnapshot(QuestionSnapshot):
    """A question snapshot plus the category chosen when the round started."""

    # Absent from rounds stored before category selection existed.
    quiz_category: NotRequired[str | None]


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(UserMixin, Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(db.String(32), unique=True)
    nickname: Mapped[str] = mapped_column(db.String(32))
    nickname_key: Mapped[str] = mapped_column(db.String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(db.String(255))
    total_score: Mapped[int] = mapped_column(default=0, index=True)
    bag: Mapped[dict[str, Any]] = mapped_column(db.JSON, default=dict)
    rounds: Mapped[list["QuizRound"]] = relationship(back_populates="user")
    __table_args__ = (CheckConstraint("total_score >= 0", name="score_nonnegative"),)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Question(Model):
    id: Mapped[str] = mapped_column(db.String(80), primary_key=True)
    category: Mapped[str] = mapped_column(db.String(64), index=True)
    difficulty: Mapped[str] = mapped_column(db.String(10))
    text: Mapped[str] = mapped_column(db.Text)
    options: Mapped[list[str]] = mapped_column(db.JSON)
    correct_index: Mapped[int] = mapped_column()
    explanation: Mapped[str] = mapped_column(db.Text)
    __table_args__ = (
        CheckConstraint(
            f"correct_index BETWEEN 0 AND {OPTION_COUNT - 1}", name="correct_range"
        ),
        CheckConstraint(
            f"difficulty IN ({', '.join(repr(value) for value in DIFFICULTIES)})",
            name="difficulty",
        ),
    )

    def snapshot(self) -> QuestionSnapshot:
        return {
            "id": self.id,
            "category": self.category,
            "difficulty": self.difficulty,
            "text": self.text,
            "options": self.options,
            "correct_index": self.correct_index,
            "explanation": self.explanation,
        }


class QuizRound(Model):
    id: Mapped[str] = mapped_column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column()
    user: Mapped[User] = relationship(back_populates="rounds")
    answers: Mapped[list["QuizAnswer"]] = relationship(
        back_populates="round",
        order_by="QuizAnswer.position",
        cascade="all, delete-orphan",
    )
    __table_args__ = (
        Index(
            "uq_active_round_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("completed_at IS NULL"),
        ),
    )


class QuizAnswer(Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[str] = mapped_column(ForeignKey("quiz_round.id"), index=True)
    position: Mapped[int] = mapped_column()
    snapshot: Mapped[AnswerSnapshot] = mapped_column(db.JSON)
    selected_option: Mapped[int | None] = mapped_column()
    awarded_points: Mapped[int] = mapped_column(default=0)
    round: Mapped[QuizRound] = relationship(back_populates="answers")
    __table_args__ = (
        UniqueConstraint("round_id", "position"),
        CheckConstraint(
            f"position BETWEEN 0 AND {ROUND_LENGTH - 1}", name="position_range"
        ),
        CheckConstraint(
            "selected_option IS NULL OR selected_option BETWEEN 0 AND "
            f"{OPTION_COUNT - 1}",
            name="option_range",
        ),
        CheckConstraint("awarded_points IN (0, 1)", name="points_range"),
        CheckConstraint(
            "selected_option IS NOT NULL OR awarded_points = 0",
            name="unanswered_score",
        ),
    )
