"""Registration and session lifecycle."""

from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.wrappers import Response

from app.auth.forms import LoginForm, RegistrationForm, validated_text
from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["GET", "POST"])
def register() -> str | Response:
    if current_user.is_authenticated:
        return redirect(url_for("quiz.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        nickname = validated_text(form.nickname)
        user = User(
            username=validated_text(form.username).lower(),
            nickname=nickname,
            nickname_key=nickname.lower(),
        )
        user.set_password(validated_text(form.password))
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Nome utente o nickname già in uso.", "error")
        else:
            session.clear()
            login_user(user)
            session.permanent = True
            return redirect(url_for("quiz.index"))
    return render_template("auth/form.html", form=form, registering=True)


@bp.route("/login", methods=["GET", "POST"])
def login() -> str | Response:
    if current_user.is_authenticated:
        return redirect(url_for("quiz.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            select(User).where(
                User.username == validated_text(form.username).lower(),
            )
        )
        if user and user.check_password(validated_text(form.password)):
            session.clear()
            login_user(user)
            session.permanent = True
            # Always use a known local landing page; ignore arbitrary next URLs.
            return redirect(url_for("quiz.index"))
        flash("Nome utente o password non validi.", "error")
    return render_template("auth/form.html", form=form, registering=False)


@bp.post("/logout")
@login_required
def logout() -> Response:
    logout_user()
    session.clear()
    return redirect(url_for("main.home"))
