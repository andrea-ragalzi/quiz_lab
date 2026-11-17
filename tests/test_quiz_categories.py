"""Category selection must change the quiz content, not only the interface."""

from html.parser import HTMLParser

import pytest
from sqlalchemy import select

from app.core.extensions import db
from app.domain.constants import CATEGORY_LABELS
from app.domain.models import QuizAnswer, QuizRound, User
from app.services.questions import import_static_questions
from tests.helpers import present


class TopicLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and "topic" in (attributes.get("class") or "").split():
            self.targets.append(attributes["href"])


@pytest.fixture
def category_client(app, client):
    with app.app_context():
        import_static_questions()
    response = client.post(
        "/auth/register",
        data={
            "username": "categorylearner",
            "nickname": "CategoryLearner",
            "password": "test-password-123",
            "confirm": "test-password-123",
        },
    )
    assert response.status_code == 302
    return client


def test_home_topics_lead_to_distinct_category_choices(client):
    parser = TopicLinks()
    parser.feed(client.get("/").get_data(as_text=True))
    assert set(parser.targets) == {
        f"/quiz/?category={category}" for category in CATEGORY_LABELS
    }


@pytest.mark.parametrize("category", CATEGORY_LABELS)
def test_chosen_category_only_assigns_matching_questions(
    app, category_client, category
):
    response = category_client.post("/quiz/start", data={"category": category})
    assert response.status_code == 302
    round_id = response.headers["Location"].rsplit("/", 1)[-1]
    with app.app_context():
        slots = db.session.scalars(
            select(QuizAnswer).where(
                QuizAnswer.round_id == round_id,
            )
        ).all()
        assert len(slots) == 10
        assert len({slot.snapshot["id"] for slot in slots}) == 10
        assert {slot.snapshot["category"] for slot in slots} == {category}


def test_picker_displays_loaded_category_and_keeps_it_on_start(category_client):
    page = category_client.get("/quiz/?category=nlp").get_data(as_text=True)
    assert 'name="category" value="nlp"' in page
    assert "25 domande" in page
    assert "Elaborazione del linguaggio naturale" in page


@pytest.mark.parametrize("path", ["/quiz/?category=unknown", "/quiz/start"])
def test_invalid_category_is_rejected_without_creating_round(
    app, category_client, path
):
    response = (
        category_client.post(path, data={"category": "unknown"})
        if path.endswith("start")
        else category_client.get(path)
    )
    assert response.status_code == 400
    with app.app_context():
        assert db.session.scalar(select(QuizRound)) is None


def test_different_category_does_not_silently_resume_or_replace_active_round(
    app,
    category_client,
):
    first = category_client.post("/quiz/start", data={"category": "python"})
    again = category_client.post("/quiz/start", data={"category": "python"})
    assert first.headers["Location"] == again.headers["Location"]
    different = category_client.post("/quiz/start", data={"category": "nlp"})
    assert different.status_code == 409
    with app.app_context():
        assert len(db.session.scalars(select(QuizRound)).all()) == 1
        assert present(db.session.scalar(select(User))).total_score == 0


def test_category_history_survives_switching_topics(app, category_client):
    from app.services.quiz import start_round, submit_answer

    with app.app_context():
        user_id = present(db.session.scalar(select(User.id)))
        python_questions = []
        for category in ("python", "nlp", "python"):
            round_id = start_round(user_id, category)
            slots = db.session.scalars(
                select(QuizAnswer)
                .where(
                    QuizAnswer.round_id == round_id,
                )
                .order_by(QuizAnswer.position)
            ).all()
            if category == "python":
                python_questions.extend(slot.snapshot["id"] for slot in slots)
            for slot in slots:
                submit_answer(
                    round_id, user_id, slot.id, slot.snapshot["correct_index"]
                )
        assert len(python_questions) == len(set(python_questions)) == 20
        assert present(db.session.get(User, user_id)).total_score == 30


def test_results_keep_the_selected_topic_in_the_summary(app, category_client):
    response = category_client.post("/quiz/start", data={"category": "python"})
    url = response.headers["Location"]
    round_id = url.rsplit("/", 1)[-1]
    with app.app_context():
        answers = [
            (slot.id, slot.snapshot["correct_index"])
            for slot in db.session.scalars(
                select(QuizAnswer)
                .where(
                    QuizAnswer.round_id == round_id,
                )
                .order_by(QuizAnswer.position)
            )
        ]
    for answer_id, option in answers:
        assert (
            category_client.post(
                f"{url}/answer",
                data={
                    "answer_id": answer_id,
                    "option": option,
                },
            ).status_code
            == 302
        )
    page = category_client.get(f"{url}/results").get_data(as_text=True)
    assert "Fondamenti di Python: hai guadagnato 10 punti" in page


def test_small_category_is_unavailable_in_picker_and_service(app, category_client):
    from sqlalchemy import delete
    from werkzeug.exceptions import Conflict

    from app.domain.models import Question
    from app.services.quiz import start_round

    with app.app_context():
        db.session.execute(
            delete(Question).where(
                Question.category == "python",
                Question.id.not_in([f"PY-{i:03}" for i in range(1, 10)]),
            )
        )
        db.session.commit()
        user_id = present(db.session.scalar(select(User.id)))
        with pytest.raises(Conflict):
            start_round(user_id, "python")
    page = category_client.get("/quiz/?category=python").get_data(as_text=True)
    assert "almeno 10 domande" in page
    assert (
        category_client.post("/quiz/start", data={"category": "python"}).status_code
        == 409
    )
