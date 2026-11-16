import pytest
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import QuizAnswer, User
from tests.helpers import present


def register(client, username="learner", nickname="Explorer"):
    return client.post(
        "/auth/register",
        data={
            "username": username,
            "nickname": nickname,
            "password": "a-long-test-password",
            "confirm": "a-long-test-password",
        },
        follow_redirects=True,
    )


def test_registration_hashes_password_and_logout_protects_quiz(app, client):
    assert register(client).status_code == 200
    with app.app_context():
        user = present(db.session.scalar(select(User)))
        assert user.username == "learner"
        assert user.password_hash != "a-long-test-password"
        assert user.check_password("a-long-test-password")
    client.post("/auth/logout")
    assert client.get("/quiz/").status_code == 302
    assert (
        client.post(
            "/auth/login",
            data={
                "username": "LEARNER",
                "password": "a-long-test-password",
            },
        ).status_code
        == 302
    )
    assert client.get("/quiz/").status_code == 200


@pytest.mark.parametrize(
    ("username", "nickname"),
    [
        ("LEARNER", "OtherName"),
        ("another", "EXPLORER"),
    ],
)
def test_duplicate_identity_is_rejected(app, client, username, nickname):
    register(client)
    client.post("/auth/logout")
    response = register(client, username, nickname)
    assert "già in uso" in response.get_data(as_text=True)
    with app.app_context():
        assert len(db.session.scalars(select(User)).all()) == 1


def test_invalid_registration_and_login_do_not_authenticate(client):
    response = client.post(
        "/auth/register",
        data={
            "username": "<bad>",
            "nickname": "Kid",
            "password": "short",
            "confirm": "other",
        },
    )
    assert response.status_code == 200
    assert client.get("/quiz/").status_code == 302
    assert (
        client.post(
            "/auth/login",
            data={
                "username": "missing",
                "password": "wrong",
            },
        ).status_code
        == 200
    )
    assert client.get("/quiz/").status_code == 302


def start(client):
    response = client.post("/quiz/start")
    assert response.status_code == 302
    return response.headers["Location"]


def test_round_scoring_persists_and_duplicate_answer_cannot_add_points(app, client):
    register(client)
    url = start(client)
    assert start(client) == url
    for position in range(10):
        with app.app_context():
            slot = present(
                db.session.scalar(
                    select(QuizAnswer).where(
                        QuizAnswer.position == position,
                    )
                )
            )
            answer_id, correct = slot.id, slot.snapshot["correct_index"]
        response = client.post(
            f"{url}/answer",
            data={
                "answer_id": answer_id,
                "option": correct,
            },
        )
        assert response.status_code == 302
        duplicate = client.post(
            f"{url}/answer",
            data={
                "answer_id": answer_id,
                "option": correct,
            },
        )
        assert duplicate.status_code == 409
    assert b"10/10" in client.get(f"{url}/results").data
    with app.app_context():
        assert present(db.session.scalar(select(User))).total_score == 10
    assert b"Explorer" in client.get("/leaderboard/").data
    assert start(client) != url


def test_foreign_round_and_invalid_option_are_rejected(app, client):
    register(client)
    url = start(client)
    with app.app_context():
        slots = db.session.scalars(
            select(QuizAnswer).order_by(QuizAnswer.position)
        ).all()
        first, later = slots[0].id, slots[1].id
    assert client.get(f"{url}/results").status_code == 409
    for value in ("-1", "4", "abc", "1.5"):
        assert (
            client.post(
                f"{url}/answer",
                data={
                    "answer_id": first,
                    "option": value,
                },
            ).status_code
            == 400
        )
    assert (
        client.post(
            f"{url}/answer",
            data={
                "answer_id": later,
                "option": "0",
            },
        ).status_code
        == 409
    )
    client.post("/auth/logout")
    register(client, "second", "SecondPlayer")
    assert client.get(url).status_code == 404
    assert (
        client.post(
            f"{url}/answer",
            data={
                "answer_id": first,
                "option": "0",
            },
        ).status_code
        == 404
    )


def test_csrf_blocks_mutations_and_external_redirect_is_ignored(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/auth/register", data={}).status_code == 400
    assert client.post("/quiz/start").status_code == 400
    app.config["WTF_CSRF_ENABLED"] = False
    register(client)
    client.post("/auth/logout")
    response = client.post(
        "/auth/login?next=https://evil.example",
        data={
            "username": "learner",
            "password": "a-long-test-password",
        },
    )
    assert response.headers["Location"] == "/quiz/"


def test_production_requires_secret_and_missing_pages_are_localized(
    monkeypatch, client
):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()
    assert client.get("/not-found").status_code == 404
    assert b"Pagina non trovata" in client.get("/not-found").data


def test_answer_key_is_not_rendered_until_submission(app, client):
    register(client)
    url = start(client)
    with app.app_context():
        slot = present(
            db.session.scalar(select(QuizAnswer).where(QuizAnswer.position == 0))
        )
        explanation = slot.snapshot["explanation"]
        answer_id = slot.id
        option = slot.snapshot["correct_index"]
    assert explanation not in client.get(url).get_data(as_text=True)
    assert client.get(f"{url}/answer").status_code == 405
    response = client.post(
        f"{url}/answer",
        data={
            "answer_id": answer_id,
            "option": option,
        },
        follow_redirects=True,
    )
    assert explanation in response.get_data(as_text=True)
    assert client.get("/auth/logout").status_code == 405


def test_large_leaderboard_page_is_rejected(client):
    assert client.get("/leaderboard/?page=99999999999999999999").status_code == 400
