"""Read-only city forecast lookup."""

from flask import Blueprint, current_app, render_template, request

from app.weather.service import Forecast, WeatherError, WeatherService

bp = Blueprint("weather", __name__, url_prefix="/weather")


@bp.get("/")
def search() -> str:
    city = request.args.get("city", "").strip()
    # ``create_app`` registers the service; extensions are stored untyped.
    service: WeatherService = current_app.extensions["weather"]
    forecast: Forecast | None = None
    error: str | None = None
    try:
        forecast = service.forecast(city)
    except WeatherError as exc:
        error = str(exc)
    return render_template(
        "home.html", forecast=forecast, city=city, weather_error=error
    )
