"""Transactional quiz progression and server-owned cumulative scoring."""

import random
from typing import Any, TypedDict

from sqlalchemy import text
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.domain import CATEGORY_LABELS, OPTION_COUNT, ROUND_LENGTH
from app.extensions import db
from app.models import AnswerSnapshot, QuizAnswer, QuizRound, utc_now
from app.quiz.draw_state import read_state, take_questions, write_state
from app.repositories.questions import QuestionRepository
from app.repositories.rounds import RoundRepository
from app.repositories.users import UserRepository


class RoundSummary(TypedDict):
    """Template values describing a round's persisted results."""

    score: int
    answered: int
    percentage: int


def owned_round(round_id: str, user_id: int) -> QuizRound:
    round_ = RoundRepository(db.session).owned(round_id, user_id)
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
    return QuestionRepository(db.session).counts_by_category()


def start_round(user_id: int, category: str | None = None) -> str:
    """Resume an active round or atomically allocate a new ten-question round."""
    validate_category(category)
    db.session.rollback()
    with db.session.begin():
        db.session.execute(text("BEGIN IMMEDIATE"))
        active = RoundRepository(db.session).active_for(user_id)
        if active:
            if category is not None and round_category(active) != category:
                raise Conflict(
                    "Completa il round in corso prima di cambiare categoria."
                )
            return active.id
        user = UserRepository(db.session).get(user_id)
        if user is None:
            raise NotFound("Utente non trovato.")
        catalog = QuestionRepository(db.session).catalog(category)
        if len(catalog) < ROUND_LENGTH:
            raise Conflict(
                f"Servono almeno {ROUND_LENGTH} domande per iniziare un round."
            )
        previous_state = read_state(user.bag, category)
        identities, state = take_questions(
            list(catalog),
            previous_state,
            ROUND_LENGTH,
            random.SystemRandom(),
        )
        user.bag = write_state(user.bag, category, state)
        snapshots: list[AnswerSnapshot] = [
            {**catalog[identity], "quiz_category": category} for identity in identities
        ]
        round_ = RoundRepository(db.session).create(user_id, snapshots)
        return round_.id


def submit_answer(round_id: str, user_id: int, answer_id: int, option: int) -> None:
    """Count an answer once, including simultaneous requests on SQLite."""
    db.session.rollback()
    with db.session.begin():
        # Acquire the write lock before reading the current answer.
        db.session.execute(text("BEGIN IMMEDIATE"))
        round_ = owned_round(round_id, user_id)
        rounds = RoundRepository(db.session)
        pending = rounds.pending_answer(round_id)
        if round_.completed_at or pending is None or pending.id != answer_id:
            raise Conflict(
                "La risposta è già registrata oppure la domanda non è quella attuale."
            )
        if type(option) is not int or option not in range(OPTION_COUNT):
            raise ValueError("Scegli una delle quattro risposte.")
        points = int(option == pending.snapshot["correct_index"])
        if not rounds.claim_answer(answer_id, option, points):
            raise Conflict("Questa risposta è già stata registrata.")
        UserRepository(db.session).add_points(user_id, points)
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


def active_round(user_id: int) -> QuizRound | None:
    return RoundRepository(db.session).active_for(user_id)


def quiz_overview(user_id: int, category: str | None) -> dict[str, Any]:
    validate_category(category)
    active = active_round(user_id)
    counts = category_counts()
    return {
        "active": active,
        "category": category,
        "categories": CATEGORY_LABELS,
        "category_counts": counts,
        "question_count": counts.get(category, 0) if category else sum(counts.values()),
        "round_length": ROUND_LENGTH,
        "active_category": round_category(active) if active else None,
    }


def current_slot(
    round_: QuizRound, feedback_id: int | None
) -> tuple[QuizAnswer, bool] | None:
    slot = next(
        (
            a
            for a in round_.answers
            if a.id == feedback_id and a.selected_option is not None
        ),
        None,
    )
    feedback = slot is not None
    if not slot:
        slot = next((a for a in round_.answers if a.selected_option is None), None)
    return (slot, feedback) if slot is not None else None


def completed_round(round_id: str, user_id: int) -> QuizRound:
    round_ = owned_round(round_id, user_id)
    if not round_.completed_at:
        raise Conflict("Completa il round prima di vedere i risultati.")
    return round_
