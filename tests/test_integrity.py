from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Conflict

from app.core.extensions import db
from app.domain.models import Question, QuizAnswer, QuizRound, User
from app.services.quiz import start_round, submit_answer
from tests.helpers import present


@pytest.fixture
def player(app):
    with app.app_context():
        user = User(username="learner", nickname="Explorer", nickname_key="explorer")
        user.set_password("a-test-password")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_simultaneous_submissions_award_one_point(app, player):
    with app.app_context():
        round_id = start_round(player)
        slot = present(
            db.session.scalar(select(QuizAnswer).where(QuizAnswer.position == 0))
        )
        answer_id, correct = slot.id, slot.snapshot["correct_index"]
    barrier = Barrier(2)

    def answer():
        with app.app_context():
            barrier.wait(timeout=5)
            try:
                submit_answer(round_id, player, answer_id, correct)
                return 302
            except Conflict:
                return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(answer) for _ in range(2)]
        outcomes = [future.result(timeout=15) for future in futures]
    assert sorted(outcomes) == [302, 409]
    with app.app_context():
        assert present(db.session.get(User, player)).total_score == 1
        assert present(db.session.get(QuizAnswer, answer_id)).awarded_points == 1


def test_concurrent_start_creates_one_active_round(app, player):
    barrier = Barrier(2)

    def start():
        with app.app_context():
            barrier.wait(timeout=5)
            return start_round(player)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(start) for _ in range(2)]
        round_ids = [future.result(timeout=15) for future in futures]
    assert round_ids[0] == round_ids[1]
    with app.app_context():
        assert len(db.session.scalars(select(QuizRound)).all()) == 1
        assert len(db.session.scalars(select(QuizAnswer)).all()) == 10


def test_wrong_answers_give_no_points_and_snapshots_survive_bank_changes(app, player):
    with app.app_context():
        round_id = start_round(player)
        slot = present(
            db.session.scalar(select(QuizAnswer).where(QuizAnswer.position == 0))
        )
        wrong = (slot.snapshot["correct_index"] + 1) % 4
        db.session.execute(delete(Question))
        db.session.commit()
        submit_answer(round_id, player, slot.id, wrong)
        assert present(db.session.get(User, player)).total_score == 0
        assert present(db.session.get(QuizAnswer, slot.id)).selected_option == wrong


def test_database_enforces_foreign_keys_unique_slots_and_score_ranges(app, player):
    with app.app_context():
        round_id = start_round(player)
        slot = present(
            db.session.scalar(select(QuizAnswer).where(QuizAnswer.position == 0))
        )
        snapshot = slot.snapshot
        db.session.add(QuizAnswer(round_id=round_id, position=0, snapshot=snapshot))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        db.session.add(QuizRound(user_id=999999))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        present(db.session.get(User, player)).total_score = -1
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_bank_is_original_sized_and_seeding_is_idempotent(app):
    from app.services.questions import import_static_questions, load_static_questions

    questions = load_static_questions()
    assert 80 <= len(questions) <= 120
    assert len({q["text"] for q in questions}) == len(questions)
    with app.app_context():
        import_static_questions()
        import_static_questions()
        assert len(db.session.scalars(select(Question)).all()) == len(questions)


def test_leaderboard_orders_points_then_nickname(app, client):
    with app.app_context():
        for name, score in [("Zebra", 10), ("Alpha", 10), ("Leader", 20)]:
            user = User(
                username=name.lower(),
                nickname=name,
                nickname_key=name.lower(),
                total_score=score,
            )
            user.set_password("long-password")
            db.session.add(user)
        db.session.commit()
    text = client.get("/leaderboard/").get_data(as_text=True)
    table = text.split('class="rank-table"', 1)[1]
    assert table.index("Leader") < table.index("Alpha") < table.index("Zebra")


def test_successive_rounds_preserve_bag_history_without_repeating(app, player):
    seen = set()
    with app.app_context():
        for _ in range(3):
            round_id = start_round(player)
            slots = db.session.scalars(
                select(QuizAnswer)
                .where(QuizAnswer.round_id == round_id)
                .order_by(QuizAnswer.position)
            ).all()
            assert not (seen & {slot.snapshot["id"] for slot in slots})
            seen.update(slot.snapshot["id"] for slot in slots)
            for slot in slots:
                submit_answer(round_id, player, slot.id, slot.snapshot["correct_index"])
        assert present(db.session.get(User, player)).total_score == 30
        assert len(seen) == 30
