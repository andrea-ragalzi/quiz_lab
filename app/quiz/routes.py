"""Quiz request validation and presentation."""

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import login_required
from werkzeug.wrappers import Response

from app.auth.identity import authenticated_user
from app.domain import OPTION_COUNT
from app.quiz.service import (
    completed_round,
    current_slot,
    owned_round,
    quiz_overview,
    round_category,
    round_summary,
    start_round,
    submit_answer,
)

bp = Blueprint("quiz", __name__, url_prefix="/quiz")


@bp.get("/")
@login_required
def index() -> str:
    category = request.args.get("category") or None
    return render_template(
        "quiz/index.html", **quiz_overview(authenticated_user().id, category)
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
    result = current_slot(round_, request.args.get("feedback", type=int))
    if result is None:
        return redirect(url_for("quiz.results", round_id=round_id))
    slot, feedback = result
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
    if option is None or option not in range(OPTION_COUNT):
        abort(400, "Scegli una delle quattro risposte.")
    if answer_id is None:
        abort(400, "Manca il riferimento alla domanda.")
    submit_answer(round_id, user_id, answer_id, option)
    return redirect(url_for("quiz.play", round_id=round_id, feedback=answer_id))


@bp.get("/<round_id>/results")
@login_required
def results(round_id: str) -> str:
    round_ = completed_round(round_id, authenticated_user().id)
    return render_template(
        "quiz/results.html",
        round=round_,
        category=round_category(round_),
        **round_summary(round_),
    )
