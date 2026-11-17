"""Public cumulative ranking."""

from flask import Blueprint, render_template, request

from app.services.leaderboard import ranking_page

bp = Blueprint("leaderboard", __name__, url_prefix="/leaderboard")


@bp.get("/")
def index() -> str:
    page = request.args.get("page", 1, type=int)
    return render_template("leaderboard.html", players=ranking_page(page))
