"""Public cumulative ranking, using one ordered database query."""

from flask import Blueprint, abort, render_template, request
from sqlalchemy import select

from app.extensions import db
from app.models import User

bp = Blueprint("leaderboard", __name__, url_prefix="/leaderboard")


@bp.get("/")
def index() -> str:
    page = max(1, request.args.get("page", 1, type=int))
    if page > 1_000_000:
        abort(400)
    players = db.paginate(
        select(User).order_by(
            User.total_score.desc(),
            User.nickname_key,
            User.id,
        ),
        page=page,
        per_page=50,
        error_out=False,
    )
    return render_template("leaderboard.html", players=players)
