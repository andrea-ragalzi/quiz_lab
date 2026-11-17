"""Registration and session lifecycle."""

from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, logout_user
from werkzeug.wrappers import Response

from app.services.auth import (
    DuplicateIdentity,
    authenticate,
    register_user,
    start_session,
)
from app.web.forms import LoginForm, RegistrationForm, validated_text

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["GET", "POST"])
def register() -> str | Response:
    if current_user.is_authenticated:
        return redirect(url_for("quiz.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = register_user(
                validated_text(form.username),
                validated_text(form.nickname),
                validated_text(form.password),
            )
        except DuplicateIdentity:
            flash("Nome utente o nickname già in uso.", "error")
        else:
            start_session(user)
            return redirect(url_for("quiz.index"))
    return render_template("auth/form.html", form=form, registering=True)


@bp.route("/login", methods=["GET", "POST"])
def login() -> str | Response:
    if current_user.is_authenticated:
        return redirect(url_for("quiz.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate(
            validated_text(form.username), validated_text(form.password)
        )
        if user:
            start_session(user)
            return redirect(url_for("quiz.index"))
        flash("Nome utente o password non validi.", "error")
    return render_template("auth/form.html", form=form, registering=False)


@bp.post("/logout")
@login_required
def logout() -> Response:
    logout_user()
    session.clear()
    return redirect(url_for("main.home"))
