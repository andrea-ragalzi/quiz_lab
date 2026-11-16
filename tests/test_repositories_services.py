import pytest
from sqlalchemy import select

from app import create_app
from app.auth.service import DuplicateIdentity, authenticate, register_user
from app.extensions import db
from app.models import AnswerSnapshot, Question, QuizAnswer, QuizRound, User
from app.quiz.service import current_slot
from app.repositories.questions import QuestionRepository
from app.repositories.rounds import RoundRepository
from app.repositories.users import UserRepository


@pytest.fixture
def memory_app():
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "repository-test",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.engine.dispose()


def test_repositories_share_transaction_and_claim_once(memory_app):
    with memory_app.app_context():
        users = UserRepository(db.session)
        questions = QuestionRepository(db.session)
        rounds = RoundRepository(db.session)
        user = User(
            username="anna", nickname="Anna", nickname_key="anna", password_hash="hash"
        )
        users.add(user)
        db.session.flush()
        question: AnswerSnapshot = {
            "id": "q1",
            "category": "python",
            "difficulty": "easy",
            "text": "Question?",
            "options": ["a", "b", "c", "d"],
            "correct_index": 0,
            "explanation": "Why",
        }
        questions.upsert_many([question])
        db.session.flush()
        assert questions.counts_by_category() == {"python": 1}
        assert questions.catalog("python")["q1"]["text"] == "Question?"
        assert questions.catalog("nlp") == {}
        round_ = rounds.create(user.id, [question])
        db.session.flush()
        assert rounds.active_for(user.id) == round_
        assert rounds.owned(round_.id, user.id) == round_
        assert rounds.owned(round_.id, user.id + 1) is None
        answer = rounds.pending_answer(round_.id)
        assert answer is not None
        assert rounds.claim_answer(answer.id, 0, 1)
        assert not rounds.claim_answer(answer.id, 1, 0)
        users.add_points(user.id, 1)
        db.session.expire_all()
        stored_user = users.get(user.id)
        assert stored_user is not None
        assert stored_user.total_score == 1
        assert users.by_username("anna") is not None
        assert list(db.session.scalars(users.ranking_query())) == [user]
        db.session.rollback()
        assert db.session.scalar(select(User)) is None
        assert db.session.scalar(select(Question)) is None
        assert rounds.active_for(user.id) is None


def test_registration_authentication_and_duplicate_rollback(memory_app):
    with memory_app.app_context():
        user = register_user("Anna", "Player", "password")
        assert user.username == "anna"
        assert authenticate("ANNA", "password") == user
        assert authenticate("anna", "wrong") is None
        assert authenticate("missing", "password") is None
        with pytest.raises(DuplicateIdentity):
            register_user("other", "PLAYER", "password")
        assert authenticate("anna", "password") is not None


def test_current_slot_feedback_and_completion():
    first = QuizAnswer(id=1, position=0, selected_option=0)
    second = QuizAnswer(id=2, position=1, selected_option=None)
    round_ = QuizRound(user_id=1, answers=[first, second])
    assert current_slot(round_, 1) == (first, True)
    assert current_slot(round_, 2) == (second, False)
    assert current_slot(round_, 999) == (second, False)
    second.selected_option = 1
    assert current_slot(round_, None) is None
    assert current_slot(round_, 1) == (first, True)
