"""Regression tests for core functionality."""

import json
import logging
import random
from datetime import UTC, datetime, time, timedelta
from html.parser import HTMLParser
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from test_weather import FIRST_DAY, GEO, WEATHER, fake_response

from app import JsonFormatter
from app.extensions import db
from app.models import QuizAnswer, User
from app.questions import STATIC_IT_PATH
from app.quiz.draw_state import take_questions
from app.weather.service import WeatherService, transform_days
from tests.helpers import present


class Elements(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.tags = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def register(client):
    assert (
        client.post(
            "/auth/register",
            data={
                "username": "testuser",
                "nickname": "AuditUser",
                "password": "test-password-123",
                "confirm": "test-password-123",
            },
        ).status_code
        == 302
    )


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/auth/login",
        "/auth/register",
        "/leaderboard/",
        "/missing",
        "/weather/?city=x",
    ],
)
def test_shared_footer(client, path):
    page = client.get(path).get_data(as_text=True)
    assert "Andrea Ragalzi" in page.split("<footer")[1]


def test_navigation_states(client):
    page = client.get("/").get_data(as_text=True).split("</nav>")[0]
    assert "Gioca al quiz" not in page
    assert 'href="/auth/login"' in page
    register(client)
    page = client.get("/").get_data(as_text=True).split("</nav>")[0]
    assert "Gioca al quiz" in page
    assert 'href="/auth/login"' not in page


def test_rotation_never_duplicates_within_round_at_refill():
    catalog = [str(n) for n in range(25)]
    for seed in range(30):
        state = {}
        rng = random.Random(seed)
        stream = []
        for _ in range(10):
            selected, state = take_questions(catalog, state, 10, rng)
            assert len(set(selected)) == 10
            stream.extend(selected)
        assert set(stream[:25]) == set(catalog)


def test_weather_uses_fixed_italian_weekdays_and_dates():
    day = transform_days(WEATHER, FIRST_DAY)[0]
    assert (
        day.name
        == (
            "Lunedì",
            "Martedì",
            "Mercoledì",
            "Giovedì",
            "Venerdì",
            "Sabato",
            "Domenica",
        )[FIRST_DAY.weekday()]
    )
    assert day.display_date == FIRST_DAY.strftime("%d/%m/%Y")


def test_weather_table_and_matching_icon(app, client):
    weather = WEATHER | {
        "hourly": WEATHER["hourly"]
        | {"weather_code": [61] * len(WEATHER["hourly"]["time"])}
    }
    app.extensions["weather"] = WeatherService(
        get=Mock(
            side_effect=[
                fake_response(GEO),
                fake_response(weather),
            ]
        )
    )
    page = client.get("/weather/?city=Roma").get_data(as_text=True)
    tags = Elements(page).tags
    assert sum(tag == "table" for tag, _ in tags) == 1
    assert sum(tag == "caption" for tag, _ in tags) == 1
    assert sum(tag == "th" and attrs.get("scope") == "row" for tag, attrs in tags) == 3
    for label in (
        "Oggi",
        "Domani",
        "Dopodomani",
        FIRST_DAY.strftime("%d/%m/%Y"),
        "Massima diurna",
        "Minima notturna",
        "Pioggia debole",
        "Open-Meteo",
    ):
        assert label in page
    assert 'class="weather-icon" aria-hidden="true">🌧' in page


def test_weather_cache_expires_at_city_midnight(monkeypatch):
    import app.weather.service as service

    clock = Mock(wraps=datetime)
    midnight = datetime.combine(
        FIRST_DAY + timedelta(days=1), time.min, ZoneInfo("Europe/Rome")
    ).astimezone(UTC)
    clock.now.return_value = midnight - timedelta(seconds=1)
    monkeypatch.setattr(service, "datetime", clock, raising=False)
    payload = WEATHER | {"timezone": "Europe/Rome"}
    get = Mock(side_effect=[fake_response(GEO), fake_response(payload)] * 2)
    weather = WeatherService(get=get)
    weather.forecast("Roma")
    weather.forecast("Roma")
    assert get.call_count == 2
    clock.now.return_value = midnight
    weather.forecast("Roma")
    assert get.call_count == 4


def test_json_logs_include_traceback():
    try:
        raise ValueError("diagnostic failure")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "test", logging.ERROR, __file__, 1, "request_failed", (), sys.exc_info()
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "Traceback" in payload["traceback"]
    assert "test_json_logs_include_traceback" in payload["traceback"]
    assert "ValueError" in payload["traceback"]


def test_json_logs_tolerate_exc_info_without_active_exception():
    # ``logger.warning(..., exc_info=True)`` outside ``except`` yields this tuple.
    record = logging.LogRecord(
        "quizlab", logging.WARNING, __file__, 1, "event", None, (None, None, None)
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload == {
        "level": "WARNING",
        "event": "event",
        "traceback": None,
        "exception_type": None,
    }


def test_authenticated_user_rejects_anonymous_requests(app):
    from werkzeug.exceptions import Unauthorized

    from app.auth.identity import authenticated_user

    with app.test_request_context(), pytest.raises(Unauthorized):
        authenticated_user()


def test_validated_text_requires_validated_field_data(app):
    from app.auth.forms import LoginForm, validated_text

    with app.test_request_context():
        form = LoginForm(data={"username": "learner"})
        assert validated_text(form.username) == "learner"
        with pytest.raises(TypeError):
            validated_text(form.password)


def test_python_025_matches_print_output():
    records = json.loads(STATIC_IT_PATH.read_text())
    question = next(q for q in records if q["id"] == "PY-025")
    assert question["options"][question["correct_index"]] == "cba"


def test_complete_italian_journey_replay_and_cumulative_score(app, client):
    register(client)
    for expected_score in (10, 20, 30):
        url = client.post("/quiz/start", data={"category": "nlp"}).headers["Location"]
        with app.app_context():
            slots = db.session.scalars(
                select(QuizAnswer)
                .where(QuizAnswer.round_id == url.rsplit("/", 1)[1])
                .order_by(QuizAnswer.position)
            ).all()
            assert len({s.snapshot["id"] for s in slots}) == 10
            assert all(s.snapshot["id"].startswith("NLP-") for s in slots)
            answers = [(s.id, s.snapshot["correct_index"]) for s in slots]
        for answer_id, option in answers:
            assert client.get(url).status_code == 200
            data = {"answer_id": answer_id, "option": option}
            assert (
                client.post(
                    url + "/answer", data=data, follow_redirects=True
                ).status_code
                == 200
            )
            assert client.post(url + "/answer", data=data).status_code == 409
        page = client.get(url + "/results").get_data(as_text=True)
        assert "10/10" in page
        assert 'name="category" value="nlp"' in page
        with app.app_context():
            assert (
                present(db.session.scalar(select(User))).total_score == expected_score
            )
    client.post("/auth/logout")
    assert client.get("/quiz/").status_code == 302
    assert (
        client.post(
            "/auth/login",
            data={
                "username": "testuser",
                "password": "test-password-123",
            },
        ).status_code
        == 302
    )
    assert b"AuditUser" in client.get("/leaderboard/").data


def test_weather_ttl_expiry_and_traceback(monkeypatch, caplog):
    import app.weather.service as service

    timer = Mock(return_value=0)
    monkeypatch.setattr(service, "monotonic", timer)
    get = Mock(side_effect=[fake_response(GEO), fake_response(WEATHER)] * 2)
    weather = WeatherService(get=get)
    weather.forecast("Roma")
    timer.return_value = 599
    weather.forecast("Roma")
    assert get.call_count == 2
    timer.return_value = 600
    weather.forecast("Roma")
    assert get.call_count == 4
    with caplog.at_level(logging.WARNING), pytest.raises(service.WeatherError):
        WeatherService(get=Mock(side_effect=ValueError("invalid upstream"))).forecast(
            "Roma"
        )
    assert caplog.records[-1].exc_info[0] is ValueError


def test_production_failure_is_italian_and_logs_traceback(app, client, caplog):
    app.config.update(TESTING=False)

    @app.get("/test-failure")
    def failure():
        raise RuntimeError("diagnostic failure")

    with caplog.at_level(logging.ERROR):
        response = client.get("/test-failure")
    page = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "Si è verificato un problema" in page
    assert "Andrea Ragalzi" in page
    assert "diagnostic failure" not in page
    assert any(r.exc_info and r.exc_info[0] is RuntimeError for r in caplog.records)


def test_default_mode_and_cli_wsgi_startup(tmp_path, monkeypatch):
    import importlib

    monkeypatch.setenv("SECRET_KEY", "isolated-production-smoke")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'production.sqlite'}")
    import wsgi

    application = importlib.reload(wsgi).application
    assert not application.debug
    assert application.config["SESSION_COOKIE_SECURE"]
    runner = application.test_cli_runner()
    for command in (
        "init-db",
        "validate-questions",
        "seed-questions",
        "seed-questions",
    ):
        result = runner.invoke(args=[command])
        assert result.exit_code == 0, result.output
    assert application.test_client().get("/").status_code == 200
    with application.app_context():
        from app.models import Question

        assert len(db.session.scalars(select(Question)).all()) == 100
        db.session.remove()
        db.engine.dispose()
