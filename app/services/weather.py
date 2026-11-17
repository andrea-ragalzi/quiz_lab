"""Open-Meteo access with bounded caching and defensive response validation."""

import logging
import math
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from threading import Lock
from time import monotonic
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT: tuple[float, float] = (3.05, 5)
CACHE_SECONDS = 600
CACHE_SIZE = 128
LOGGER = logging.getLogger(__name__)
CONDITIONS = {
    0: ("Sereno", "☀"),
    1: ("Prevalentemente sereno", "🌤"),
    2: ("Parzialmente nuvoloso", "⛅"),
    3: ("Coperto", "☁"),
    45: ("Nebbia", "🌫"),
    48: ("Nebbia con brina", "🌫"),
    51: ("Pioviggine debole", "🌦"),
    53: ("Pioviggine moderata", "🌦"),
    55: ("Pioviggine intensa", "🌧"),
    56: ("Pioviggine gelata", "🌧"),
    57: ("Pioviggine gelata intensa", "🌧"),
    61: ("Pioggia debole", "🌧"),
    63: ("Pioggia moderata", "🌧"),
    65: ("Pioggia intensa", "🌧"),
    66: ("Pioggia gelata", "🌧"),
    67: ("Pioggia gelata intensa", "🌧"),
    71: ("Neve debole", "❄"),
    73: ("Neve moderata", "❄"),
    75: ("Neve intensa", "❄"),
    77: ("Nevischio", "❄"),
    80: ("Rovesci deboli", "🌦"),
    81: ("Rovesci moderati", "🌧"),
    82: ("Rovesci intensi", "🌧"),
    85: ("Rovesci di neve deboli", "❄"),
    86: ("Rovesci di neve intensi", "❄"),
    95: ("Temporale", "⛈"),
    96: ("Temporale con grandine", "⛈"),
    99: ("Forte temporale con grandine", "⛈"),
}


WEEKDAYS = (
    "Lunedì",
    "Martedì",
    "Mercoledì",
    "Giovedì",
    "Venerdì",
    "Sabato",
    "Domenica",
)


class WeatherError(ValueError):
    """A safe message for a weather lookup failure."""


QueryParams = Mapping[str, str | int | float]


class JsonResponse(Protocol):
    """The subset of ``requests.Response`` used by the service."""

    def raise_for_status(self) -> None: ...

    def json(self) -> Any: ...


class HttpGet(Protocol):
    """A ``requests.get``-compatible callable, injectable for tests."""

    def __call__(
        self, url: str, *, params: QueryParams, timeout: tuple[float, float]
    ) -> JsonResponse: ...


@dataclass(frozen=True)
class ForecastDay:
    date: str
    name: str
    maximum: float
    minimum: float
    condition: str
    icon: str

    @property
    def display_date(self) -> str:
        day = date.fromisoformat(self.date)
        return f"{day.day:02d}/{day.month:02d}/{day.year}"


@dataclass(frozen=True)
class Forecast:
    city: str
    days: tuple[ForecastDay, ...]


def _number(value: object, lower: float, upper: float) -> float:
    """Validate a JSON number; ``bool`` and other subclasses are rejected."""
    if type(value) is not int and type(value) is not float:
        raise ValueError("Invalid numeric weather data.")
    if not math.isfinite(value):
        raise ValueError("Invalid numeric weather data.")
    if not lower <= value <= upper:
        raise ValueError("Weather value outside supported range.")
    return value


def transform_days(
    payload: Mapping[str, Any], first_day: date
) -> tuple[ForecastDay, ...]:
    """Use local 06-18 daytime and 18-06 following-night hourly extrema."""
    zone = ZoneInfo(payload["timezone"])
    hourly = payload["hourly"]
    times = hourly["time"]
    temperatures = hourly["temperature_2m"]
    codes = hourly["weather_code"]
    if not all(isinstance(values, list) for values in (times, temperatures, codes)):
        raise ValueError("Expected hourly arrays.")
    if not len(times) == len(temperatures) == len(codes):
        raise ValueError("Hourly arrays must have equal lengths.")
    readings: dict[datetime, tuple[float, int]] = {}
    for timestamp, temperature, code in zip(times, temperatures, codes, strict=True):
        if type(timestamp) is not int or type(code) is not int:
            raise ValueError("Invalid hourly timestamp or weather code.")
        instant = datetime.fromtimestamp(timestamp, UTC)
        if instant in readings:
            raise ValueError("Duplicate hourly timestamp.")
        readings[instant] = (_number(temperature, -100, 70), code)

    if not readings:
        raise ValueError("Empty hourly forecast.")
    first_reading, last_reading = min(readings), max(readings)

    def period(start: datetime, end: datetime) -> list[tuple[float, int]]:
        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        if first_reading > start_utc or last_reading < end_utc - timedelta(hours=1):
            raise ValueError("Incomplete hourly forecast.")
        steps = math.ceil((start_utc - first_reading).total_seconds() / 3600)
        current = first_reading + timedelta(hours=steps)
        result: list[tuple[float, int]] = []
        while current < end_utc:
            if current not in readings:
                raise ValueError("Missing hourly reading.")
            result.append(readings[current])
            current += timedelta(hours=1)
        if not result:
            raise ValueError("Empty forecast period.")
        return result

    days: list[ForecastDay] = []
    for offset in range(3):
        day = first_day + timedelta(days=offset)
        day_start = datetime(day.year, day.month, day.day, 6, tzinfo=zone)
        night_start = day_start.replace(hour=18)
        next_day = day + timedelta(days=1)
        night_end = datetime(
            next_day.year, next_day.month, next_day.day, 6, tzinfo=zone
        )
        daytime = period(day_start, night_start)
        nighttime = period(night_start, night_end)
        label, icon = CONDITIONS.get(
            daytime[len(daytime) // 2][1], ("Condizioni non disponibili", "☁")
        )
        days.append(
            ForecastDay(
                day.isoformat(),
                WEEKDAYS[day.weekday()],
                max(v for v, _ in daytime),
                min(v for v, _ in nighttime),
                label,
                icon,
            )
        )
    return tuple(days)


class WeatherService:
    """Resolve a city and return its cached three-day forecast."""

    def __init__(self, get: HttpGet | None = None) -> None:
        self._get: HttpGet = get or requests.get
        self._cache: OrderedDict[str, tuple[float, Forecast, ZoneInfo, date]] = (
            OrderedDict()
        )
        self._lock = Lock()

    def _json(self, url: str, params: QueryParams) -> dict[str, Any]:
        response = self._get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object.")
        return payload

    def forecast(self, city: str) -> Forecast:
        city = city.strip()
        if not 2 <= len(city) <= 80:
            raise WeatherError("Inserisci una città usando da 2 a 80 caratteri.")
        key = city.casefold()
        with self._lock:
            cached = self._cache.get(key)
            if (
                cached
                and cached[0] > monotonic()
                and datetime.now(UTC).astimezone(cached[2]).date() == cached[3]
            ):
                self._cache.move_to_end(key)
                return cached[1]
        try:
            geo = self._json(
                GEOCODING_URL,
                {
                    "name": city,
                    "count": 1,
                    "language": "it",
                    "format": "json",
                },
            )
            results = geo.get("results", [])
            if not results:
                raise WeatherError(
                    "Città non trovata. Prova una città vicina o controlla il nome."
                )
            place = results[0]
            latitude = _number(place["latitude"], -90, 90)
            longitude = _number(place["longitude"], -180, 180)
            name = place["name"]
            country = place.get("country", "")
            if not isinstance(name, str) or not isinstance(country, str) or not name:
                raise ValueError("Invalid city name.")
            weather = self._json(
                FORECAST_URL,
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": "auto",
                    "hourly": "temperature_2m,weather_code",
                    "timeformat": "unixtime",
                    "forecast_days": 5,
                    "temperature_unit": "celsius",
                },
            )
            city_zone = ZoneInfo(weather.get("timezone", place.get("timezone", "UTC")))
            fetched_day = datetime.now(UTC).astimezone(city_zone).date()
            result = Forecast(
                ", ".join(filter(None, (name, country))),
                transform_days(weather, fetched_day),
            )
        except WeatherError:
            raise
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
            OverflowError,
            OSError,
        ):
            LOGGER.warning("weather_upstream_unavailable", exc_info=True)
            raise WeatherError(
                "Il meteo non è disponibile al momento. Riprova più tardi."
            ) from None
        with self._lock:
            self._cache[key] = (
                monotonic() + CACHE_SECONDS,
                result,
                city_zone,
                fetched_day,
            )
            self._cache.move_to_end(key)
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return result
