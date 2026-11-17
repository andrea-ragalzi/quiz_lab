from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
import requests

from app.services.weather import WeatherError, WeatherService

GEO = {
    "results": [
        {
            "name": "London",
            "country": "United Kingdom",
            "latitude": 51.5,
            "longitude": -0.12,
        }
    ]
}
FIRST_DAY = datetime.now(UTC).date()
START = datetime(FIRST_DAY.year, FIRST_DAY.month, FIRST_DAY.day, tzinfo=UTC)
HOURS = [START + timedelta(hours=i) for i in range(120)]
WEATHER = {
    "timezone": "UTC",
    "hourly": {
        "time": [int(t.timestamp()) for t in HOURS],
        "temperature_2m": [12.5 if 6 <= t.hour < 18 else 7 for t in HOURS],
        "weather_code": [
            0
            if t.day == FIRST_DAY.day
            else (3 if t.date() == FIRST_DAY + timedelta(days=1) else 61)
            for t in HOURS
        ],
    },
}


def fake_response(payload):
    response = Mock()
    response.json.return_value = payload
    return response


def test_forecast_resolves_city_transforms_three_days_and_caches():
    get = Mock(side_effect=[fake_response(GEO), fake_response(WEATHER)])
    service = WeatherService(get=get)
    result = service.forecast(" London ")
    assert result.city == "London, United Kingdom"
    assert len(result.days) == 3
    assert result.days[0].date == FIRST_DAY.isoformat()
    assert result.days[0].maximum == 12.5
    assert result.days[0].minimum == 7
    assert result.days[0].condition == "Sereno"
    assert result.days[2].condition == "Pioggia debole"
    assert service.forecast("london") == result
    assert get.call_count == 2
    assert get.call_args_list[0].kwargs["timeout"] == (3.05, 5)
    assert get.call_args_list[1].kwargs["params"]["forecast_days"] == 5
    assert get.call_args_list[1].kwargs["params"]["timeformat"] == "unixtime"


@pytest.mark.parametrize("payload", [{}, {"results": []}])
def test_missing_city_has_meaningful_error(payload):
    service = WeatherService(get=Mock(return_value=fake_response(payload)))
    with pytest.raises(WeatherError, match="non trovata"):
        service.forecast("Nowhere")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"hourly": {}},
        WEATHER | {"hourly": WEATHER["hourly"] | {"time": []}},
        WEATHER | {"hourly": WEATHER["hourly"] | {"temperature_2m": [None] * 120}},
        WEATHER
        | {"hourly": WEATHER["hourly"] | {"temperature_2m": [float("nan")] * 120}},
        WEATHER | {"hourly": WEATHER["hourly"] | {"weather_code": [None] * 120}},
    ],
)
def test_malformed_forecast_does_not_leak_internal_errors(payload):
    service = WeatherService(
        get=Mock(
            side_effect=[
                fake_response(GEO),
                fake_response(payload),
            ]
        )
    )
    with pytest.raises(WeatherError, match="non è disponibile"):
        service.forecast("London")


@pytest.mark.parametrize(
    "failure",
    [requests.Timeout, requests.HTTPError, requests.ConnectionError, ValueError],
)
def test_upstream_failures_are_safe(failure):
    get = Mock(side_effect=failure("private upstream details"))
    with pytest.raises(WeatherError, match="non è disponibile") as error:
        WeatherService(get=get).forecast("London")
    assert "private" not in str(error.value)


@pytest.mark.parametrize("city", ["", "x", "a" * 81])
def test_invalid_city_is_rejected_before_network_call(city):
    get = Mock()
    with pytest.raises(WeatherError, match="2 a 80"):
        WeatherService(get=get).forecast(city)
    get.assert_not_called()


def test_hourly_temperatures_cover_day_and_following_night_across_dst():
    from datetime import UTC, date, datetime, timedelta
    from zoneinfo import ZoneInfo

    from app.services.weather import transform_days

    zone = ZoneInfo("Europe/Rome")
    start = datetime(2026, 3, 27, 23, tzinfo=UTC)
    times = [start + timedelta(hours=i) for i in range(96)]
    temperatures = []
    codes = []
    for instant in times:
        local = instant.astimezone(zone)
        temperatures.append(30 if local.hour == 12 else (-4 if local.hour == 2 else 8))
        codes.append(0)
    payload = {
        "timezone": "Europe/Rome",
        "hourly": {
            "time": [int(t.timestamp()) for t in times],
            "temperature_2m": temperatures,
            "weather_code": codes,
        },
    }
    days = transform_days(payload, date(2026, 3, 28))
    assert [d.date for d in days] == ["2026-03-28", "2026-03-29", "2026-03-30"]
    assert days[0].maximum == 30
    assert days[0].minimum == 8  # 02:00 does not exist on DST transition night.
    assert days[1].minimum == -4  # 02:00 the following night exists.


def test_missing_hourly_readings_are_rejected():
    from datetime import date

    from app.services.weather import transform_days

    with pytest.raises(ValueError):
        transform_days(
            {
                "timezone": "Europe/Rome",
                "hourly": {"time": [], "temperature_2m": [], "weather_code": []},
            },
            date(2026, 3, 28),
        )


def test_half_hour_dst_transition_uses_hourly_readings():
    from datetime import date

    from app.services.weather import transform_days

    start = datetime(2026, 10, 2, 13, 30, tzinfo=UTC)
    times = [start + timedelta(hours=i) for i in range(100)]
    payload = {
        "timezone": "Australia/Lord_Howe",
        "hourly": {
            "time": [int(t.timestamp()) for t in times],
            "temperature_2m": [12.0] * len(times),
            "weather_code": [0] * len(times),
        },
    }
    days = transform_days(payload, date(2026, 10, 3))
    assert len(days) == 3
    assert all(day.maximum == 12 and day.minimum == 12 for day in days)


def test_missing_single_hour_results_in_safe_error():
    hourly = {key: value.copy() for key, value in WEATHER["hourly"].items()}
    for values in hourly.values():
        values.pop(12)
    get = Mock(
        side_effect=[fake_response(GEO), fake_response(WEATHER | {"hourly": hourly})]
    )
    with pytest.raises(WeatherError, match="non è disponibile"):
        WeatherService(get=get).forecast("London")
