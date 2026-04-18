from typing import Any

QUESTION_TEMPLATES = [
    "It is {date}, {season} in Finland (lat {lat}, lng {lng}), currently {temp}°C. "
    "What is the single most important task a small-scale farmer or gardener should do today?",

    "Given it is {season} and the temperature is {temp}°C with a 3-day forecast of {forecast}, "
    "what watering or irrigation adjustments should a gardener make right now?",

    "It is day {doy} of the year in Finland. What crops or seeds should a farmer be considering "
    "planting, sowing, or transplanting this week?",

    "The current weather in Finland is {temp}°C, wind {wind} km/h, precipitation {precip} mm. "
    "What pests or plant diseases are most likely to be active and what should a gardener watch for?",

    "It is {season} in Finland. What soil preparation or amendment tasks would give the biggest "
    "return right now for a small farm or kitchen garden?",

    "Given the 3-day forecast of {forecast} in Finland, what harvest tasks should a farmer "
    "prioritise or prepare for this week?",

    "It is {date} in Finland. What is one companion planting technique or beneficial "
    "insect habitat improvement a gardener could realistically do today?",

    "The season is {season} in Finland with current temp {temp}°C. "
    "What food preservation or storage tasks are most timely for a small-scale producer right now?",

    "It is {season} in Finland, day {doy} of the year. What perennial or heritage plant care "
    "tasks are most important at this point in the growing season?",

    "Given today is {date} and current conditions are {temp}°C, {wind} km/h wind, "
    "what is one practical way a small-scale farmer can improve soil health today?",
]


def _fmt_forecast(forecast_days: list[dict]) -> str:
    if not forecast_days:
        return "unknown"
    parts = []
    for d in forecast_days:
        parts.append(f"{d['date']}: {d['min_c']}–{d['max_c']}°C, {d['precip_mm']}mm rain")
    return "; ".join(parts)


def generate_questions(context: dict[str, Any]) -> list[str]:
    weather = context.get("weather", {})
    forecast = _fmt_forecast(weather.get("forecast_3day", []))
    loc = context.get("location", {})

    values = {
        "date": context.get("date", "today"),
        "season": context.get("season", "unknown season"),
        "doy": context.get("day_of_year", "?"),
        "temp": weather.get("current_temp_c", "?"),
        "wind": weather.get("wind_kmh", "?"),
        "precip": weather.get("precipitation_mm", "?"),
        "forecast": forecast,
        "lat": loc.get("lat", "?"),
        "lng": loc.get("lng", "?"),
    }

    return [t.format(**values) for t in QUESTION_TEMPLATES]
