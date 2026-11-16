"""Import behavior, atomic validation and preservation of existing gameplay."""

import json
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Question, QuizAnswer, QuizRound, User
from app.questions import import_static_questions
from app.quiz.service import start_round, submit_answer
from tests.helpers import present

ARCHIVE = Path(__file__).resolve().parents[1] / "data" / "questions_it.json"


def test_italian_archive_is_imported_idempotently_without_changing_progress(app):
    with app.app_context():
        user = User(
            username="importlearner", nickname="Importer", nickname_key="importer"
        )
        user.set_password("original-password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        round_id = start_round(user_id)
        slot = present(
            db.session.scalar(select(QuizAnswer).where(QuizAnswer.position == 0))
        )
        submit_answer(round_id, user_id, slot.id, slot.snapshot["correct_index"])
        before = [
            (a.id, a.snapshot, a.selected_option, a.awarded_points)
            for a in db.session.scalars(select(QuizAnswer).order_by(QuizAnswer.id))
        ]
        password_hash = present(db.session.get(User, user_id)).password_hash
        assert import_static_questions(ARCHIVE) == 100
        assert import_static_questions(ARCHIVE) == 100
        imported = db.session.scalars(
            select(Question).where(
                Question.id.like("PY-%")
                | Question.id.like("CV-%")
                | Question.id.like("NLP-%")
                | Question.id.like("ML-%")
            )
        ).all()
        assert Counter(q.category for q in imported) == {
            "python": 25,
            "computer_vision": 25,
            "nlp": 25,
            "machine_learning": 25,
        }
        question = present(db.session.get(Question, "PY-001"))
        assert question.difficulty == "easy"
        assert "Quale risultato stampa questa espressione?" in question.text
        assert "In Python la moltiplicazione" in question.explanation
        assert "print(2 + 3 * 4)" in question.text
        assert question.options[question.correct_index] == "14"
        assert present(db.session.get(User, user_id)).password_hash == password_hash
        assert present(db.session.get(User, user_id)).total_score == 1
        assert present(db.session.get(QuizRound, round_id)).completed_at is None
        assert [
            (a.id, a.snapshot, a.selected_option, a.awarded_points)
            for a in db.session.scalars(select(QuizAnswer).order_by(QuizAnswer.id))
        ] == before


@pytest.mark.parametrize(
    "mutation",
    [
        {"options": ["same", "same", "three", "four"]},
        {"correct_index": True},
        {"correct_index": 4},
        {"description": ""},
        {"code": 123},
        {"difficulty": "unknown"},
        {"category": "unknown"},
    ],
)
def test_invalid_import_is_rejected_before_any_update(app, tmp_path, mutation):
    records = json.loads(ARCHIVE.read_text())
    records[0]["title"] = "This update must not be persisted"
    records[-1].update(mutation)
    broken = tmp_path / "invalid.json"
    broken.write_text(json.dumps(records))
    with app.app_context():
        before = {q.id: q.snapshot() for q in db.session.scalars(select(Question))}
        with pytest.raises(ValueError):
            import_static_questions(broken)
        after = {q.id: q.snapshot() for q in db.session.scalars(select(Question))}
        assert after == before
        assert len(after) == 100


def test_upsert_updates_bank_but_not_assigned_snapshot(app, tmp_path):
    records = json.loads(ARCHIVE.read_text())
    with app.app_context():
        import_static_questions(ARCHIVE)
        user = User(username="snapshot", nickname="Snapshot", nickname_key="snapshot")
        user.set_password("original-password")
        db.session.add(user)
        db.session.flush()
        round_ = QuizRound(user_id=user.id)
        db.session.add(round_)
        db.session.flush()
        snapshot = present(db.session.get(Question, "PY-001")).snapshot()
        slot = QuizAnswer(round_id=round_.id, position=0, snapshot=snapshot)
        db.session.add(slot)
        db.session.commit()
        answer_id = slot.id
        records[0]["title"] = "Updated title"
        updated = tmp_path / "updated.json"
        updated.write_text(json.dumps(records))
        import_static_questions(updated)
        assert present(db.session.get(Question, "PY-001")).text.startswith(
            "Updated title"
        )
        assert present(db.session.get(QuizAnswer, answer_id)).snapshot == snapshot


def test_static_mode_uses_only_imported_questions_and_hides_explanations(app):
    with app.app_context():
        import_static_questions(ARCHIVE)
        user = User(
            username="staticonly", nickname="StaticOnly", nickname_key="staticonly"
        )
        user.set_password("original-password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        round_id = start_round(user_id)
        slots = db.session.scalars(
            select(QuizAnswer)
            .where(
                QuizAnswer.round_id == round_id,
            )
            .order_by(QuizAnswer.position)
        ).all()
        assert len(slots) == 10
        assert len({slot.snapshot["id"] for slot in slots}) == 10
        assert all(
            slot.snapshot["category"]
            in {
                "python",
                "computer_vision",
                "nlp",
                "machine_learning",
            }
            for slot in slots
        )
        first_id = slots[0].id
        question_text = slots[0].snapshot["text"]
        explanation = slots[0].snapshot["explanation"]
        correct = slots[0].snapshot["correct_index"]
    client = app.test_client()
    client.post(
        "/auth/login",
        data={
            "username": "staticonly",
            "password": "original-password",
        },
    )
    page = client.get(f"/quiz/{round_id}").get_data(as_text=True)
    from markupsafe import escape

    assert str(escape(question_text)) in page
    assert str(escape(explanation)) not in page
    after = client.post(
        f"/quiz/{round_id}/answer",
        data={
            "answer_id": first_id,
            "option": correct,
        },
        follow_redirects=True,
    ).get_data(as_text=True)
    assert str(escape(explanation)) in after


@pytest.mark.parametrize(
    "route", ["/", "/auth/login", "/auth/register", "/leaderboard/"]
)
def test_frontend_declares_italian_language(client, route):
    page = client.get(route).get_data(as_text=True)
    assert '<html lang="it">' in page


def test_static_description_is_only_in_explanation():
    from app.questions import load_static_questions

    records = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    questions = load_static_questions(ARCHIVE)
    for record, question in zip(records, questions, strict=True):
        assert record["description"] not in question["text"]
        assert record["description"] in question["explanation"]
        if record["code"]:
            assert record["code"] in question["text"]


def test_mixed_round_excludes_old_questions(app):
    app.config["QUIZ_MODE"] = "mixed"
    with app.app_context():
        for i in range(100):
            db.session.add(
                Question(
                    id=f"old-{i}",
                    category="Legacy",
                    difficulty="easy",
                    text="Old question",
                    options=["a", "b", "c", "d"],
                    correct_index=0,
                    explanation="Old",
                )
            )
        user = User(username="catalogcheck", nickname="Catalog", nickname_key="catalog")
        user.set_password("original-password")
        db.session.add(user)
        db.session.commit()
        round_id = start_round(user.id)
        slots = db.session.scalars(
            select(QuizAnswer).where(QuizAnswer.round_id == round_id)
        ).all()
        assert all(
            slot.snapshot["category"]
            in {"python", "computer_vision", "nlp", "machine_learning"}
            for slot in slots
        )


def test_invalid_category_shows_specific_error(client):
    client.post(
        "/auth/register",
        data={
            "username": "testcategory",
            "nickname": "Category",
            "password": "test-password-123",
            "confirm": "test-password-123",
        },
    )
    page = client.get("/quiz/?category=unknown").get_data(as_text=True)
    assert "Scegli una delle quattro categorie disponibili." in page
