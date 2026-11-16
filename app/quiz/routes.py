"""Quiz request validation and presentation."""

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import select
from werkzeug.wrappers import Response

from app.auth.identity import authenticated_user
from app.extensions import db
from app.models import QuizRound
from app.questions import CATEGORY_LABELS
from app.quiz.service import (
    ROUND_LENGTH,
    category_counts,
    owned_round,
    round_category,
    round_summary,
    start_round,
    submit_answer,
    validate_category,
)

bp = Blueprint("quiz", __name__, url_prefix="/quiz")


@bp.get("/")
@login_required
def index() -> str:
    category = request.args.get("category") or None
    validate_category(category)
    active = db.session.scalar(
        select(QuizRound).where(
            QuizRound.user_id == authenticated_user().id,
            QuizRound.completed_at.is_(None),
        )
    )
    counts = category_counts()
    return render_template(
        "quiz/index.html",
        active=active,
        category=category,
        categories=CATEGORY_LABELS,
        category_counts=counts,
        question_count=counts.get(category, 0) if category else sum(counts.values()),
        round_length=ROUND_LENGTH,
        active_category=round_category(active) if active else None,
    )


@bp.post("/start")
@login_required
def start() -> Response:
    round_id = start_round(
        authenticated_user().id, request.form.get("category") or None
    )
    return redirect(url_for("quiz.play", round_id=round_id))


@bp.get("/<round_id>")
@login_required
def play(round_id: str) -> str | Response:
    round_ = owned_round(round_id, authenticated_user().id)
    answers = round_.answers
    feedback_id = request.args.get("feedback", type=int)
    slot = next(
        (a for a in answers if a.id == feedback_id and a.selected_option is not None),
        None,
    )
    feedback = slot is not None
    if not slot:
        slot = next((a for a in answers if a.selected_option is None), None)
    if slot is None:
        return redirect(url_for("quiz.results", round_id=round_id))
    return render_template(
        "quiz/play.html",
        round=round_,
        slot=slot,
        feedback=feedback,
        category=round_category(round_),
        **round_summary(round_),
    )


@bp.post("/<round_id>/answer")
@login_required
def answer(round_id: str) -> Response:
    user_id = authenticated_user().id
    owned_round(round_id, user_id)
    option = request.form.get("option", type=int)
    answer_id = request.form.get("answer_id", type=int)
    if option is None or option not in range(4):
        abort(400, "Scegli una delle quattro risposte.")
    if answer_id is None:
        abort(400, "Manca il riferimento alla domanda.")
    submit_answer(round_id, user_id, answer_id, option)
    return redirect(url_for("quiz.play", round_id=round_id, feedback=answer_id))


@bp.get("/<round_id>/results")
@login_required
def results(round_id: str) -> str:
    round_ = owned_round(round_id, authenticated_user().id)
    if not round_.completed_at:
        abort(409, "Completa il round prima di vedere i risultati.")
    return render_template(
        "quiz/results.html",
        round=round_,
        category=round_category(round_),
        **round_summary(round_),
    )
