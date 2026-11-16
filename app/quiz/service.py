"""Transactional quiz progression and server-owned cumulative scoring."""

import hashlib
import random
from collections.abc import Mapping
from typing import Any, TypedDict

from sqlalchemy import func, select, text, update
from sqlalchemy.engine import CursorResult
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.extensions import db
from app.models import Question, QuizAnswer, QuizRound, User, utc_now
from app.questions import CATEGORY_LABELS

ROUND_LENGTH = 10


class DrawState(TypedDict):
    """Persisted progress through a shuffled question catalog."""

    version: str
    remaining: list[str]
    last: str | None


class RoundSummary(TypedDict):
    """Template values describing a round's persisted results."""

    score: int
    answered: int
    percentage: int


def take_questions(
    catalog: list[str],
    state: Mapping[str, Any],
    count: int,
    rng: random.Random,
) -> tuple[list[str], DrawState]:
    """Draw without replacement; retain bounded state across successive rounds."""
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or not 0 <= count <= len(catalog)
    ):
        raise ValueError("A unique catalog and a count within its size are required.")
    version = hashlib.sha256("\n".join(sorted(catalog)).encode()).hexdigest()
    remaining = (
        list(state.get("remaining", [])) if state.get("version") == version else []
    )
    last = state.get("last")
    selected: list[str] = []
    for _ in range(count):
        if not remaining:
            remaining = list(catalog)
            rng.shuffle(remaining)
            if len(remaining) > 1 and remaining[-1] == last:
                remaining[0], remaining[-1] = remaining[-1], remaining[0]
        # Keep questions already selected for a later round.
        index = next(
            i for i in range(len(remaining) - 1, -1, -1) if remaining[i] not in selected
        )
        last = remaining.pop(index)
        selected.append(last)
    return selected, {"version": version, "remaining": remaining, "last": last}


def owned_round(round_id: str, user_id: int) -> QuizRound:
    round_ = db.session.scalar(
        select(QuizRound).where(
            QuizRound.id == round_id,
            QuizRound.user_id == user_id,
        )
    )
    if round_ is None:
        raise NotFound("Round non trovato.")
    return round_


def validate_category(category: str | None) -> None:
    if category is not None and category not in CATEGORY_LABELS:
        raise BadRequest("Scegli una delle quattro categorie disponibili.")


def round_category(round_: QuizRound) -> str | None:
    """Return the category selected for the round."""
    return round_.answers[0].snapshot.get("quiz_category") if round_.answers else None


def category_counts() -> dict[str, int]:
    return dict(
        db.session.execute(
            select(Question.category, func.count(Question.id))
            .where(Question.category.in_(CATEGORY_LABELS))
            .group_by(Question.category)
        ).all()
    )


def start_round(user_id: int, category: str | None = None) -> str:
    """Resume an active round or atomically allocate a new ten-question round."""
    validate_category(category)
    db.session.rollback()
    with db.session.begin():
        db.session.execute(text("BEGIN IMMEDIATE"))
        active = db.session.scalar(
            select(QuizRound).where(
                QuizRound.user_id == user_id,
                QuizRound.completed_at.is_(None),
            )
        )
        if active:
            if category is not None and round_category(active) != category:
                raise Conflict(
                    "Completa il round in corso prima di cambiare categoria."
                )
            return active.id
        user = db.session.get(User, user_id)
        if user is None:
            raise NotFound("Utente non trovato.")
        query = select(Question)
        if category is not None:
            query = query.where(Question.category == category)
        else:
            query = query.where(Question.category.in_(CATEGORY_LABELS))
        catalog = {q.id: q.snapshot() for q in db.session.scalars(query)}
        if len(catalog) < ROUND_LENGTH:
            raise Conflict("Servono almeno 10 domande per iniziare un round.")
        topic_bags = dict(user.bag.get("categories", {}))
        previous_state = topic_bags.get(category, {}) if category else user.bag
        identities, state = take_questions(
            list(catalog),
            previous_state,
            ROUND_LENGTH,
            random.SystemRandom(),
        )
        if category:
            topic_bags[category] = state
            user.bag = {**user.bag, "categories": topic_bags}
        else:
            user.bag = {**user.bag, **state}
        round_ = QuizRound(user_id=user_id)
        db.session.add(round_)
        db.session.flush()
        for position, identity in enumerate(identities):
            db.session.add(
                QuizAnswer(
                    round_id=round_.id,
                    position=position,
                    snapshot={**catalog[identity], "quiz_category": category},
                )
            )
        return round_.id


def submit_answer(round_id: str, user_id: int, answer_id: int, option: int) -> None:
    """Count an answer once, including simultaneous requests on SQLite."""
    db.session.rollback()
    with db.session.begin():
        # Acquire the write lock before reading the current answer.
        db.session.execute(text("BEGIN IMMEDIATE"))
        round_ = owned_round(round_id, user_id)
        pending = db.session.scalar(
            select(QuizAnswer)
            .where(
                QuizAnswer.round_id == round_id,
                QuizAnswer.selected_option.is_(None),
            )
            .order_by(QuizAnswer.position)
        )
        if round_.completed_at or pending is None or pending.id != answer_id:
            raise Conflict(
                "La risposta è già registrata oppure la domanda non è quella attuale."
            )
        if type(option) is not int or option not in range(4):
            raise ValueError("Scegli una delle quattro risposte.")
        points = int(option == pending.snapshot["correct_index"])
        claimed = db.session.execute(
            update(QuizAnswer)
            .where(
                QuizAnswer.id == answer_id,
                QuizAnswer.selected_option.is_(None),
            )
            .values(selected_option=option, awarded_points=points)
        )
        # DML executes through a cursor, but ``Session.execute()`` is annotated
        # with the base ``Result`` type, which has no ``rowcount``.
        if not isinstance(claimed, CursorResult):
            raise TypeError("UPDATE did not return a cursor result.")
        if claimed.rowcount != 1:
            raise Conflict("Questa risposta è già stata registrata.")
        db.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                total_score=User.total_score + points,
            )
        )
        if pending.position == ROUND_LENGTH - 1:
            round_.completed_at = utc_now()


def round_summary(round_: QuizRound) -> RoundSummary:
    """Summarize persisted results without trusting any browser-provided totals."""
    score = sum(answer.awarded_points for answer in round_.answers)
    return {
        "score": score,
        "answered": sum(
            answer.selected_option is not None for answer in round_.answers
        ),
        "percentage": score * 100 // ROUND_LENGTH,
    }
