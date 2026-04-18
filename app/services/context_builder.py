import datetime
import requests


SEASONS = {
    (12, 1, 2): "winter",
    (3, 4, 5): "spring",
    (6, 7, 8): "summer",
    (9, 10, 11): "autumn",
}


def _season(month: int) -> str:
    for months, name in SEASONS.items():
        if month in months:
            return name
    return "unknown"


def _fetch_weather(lat: float, lng: float) -> dict:
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lng}"
            "&current=temperature_2m,weathercode,windspeed_10m,precipitation"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
            "&timezone=auto&forecast_days=3"
        )
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        current = data.get("current", {})
        daily = data.get("daily", {})
        return {
            "current_temp_c": current.get("temperature_2m"),
            "wind_kmh": current.get("windspeed_10m"),
            "precipitation_mm": current.get("precipitation"),
            "weathercode": current.get("weathercode"),
            "forecast_3day": [
                {
                    "date": daily["time"][i],
                    "max_c": daily["temperature_2m_max"][i],
                    "min_c": daily["temperature_2m_min"][i],
                    "precip_mm": daily["precipitation_sum"][i],
                }
                for i in range(min(3, len(daily.get("time", []))))
            ],
        }
    except Exception:
        return {"error": "weather unavailable"}


def build_context(lat: float = 60.38, lng: float = 24.51, node_name: str = "farm") -> dict:
    """
    Build a frozen context snapshot for a tip session.
    Default coords: Hyvinkää, Finland.
    """
    now = datetime.datetime.now()
    weather = _fetch_weather(lat, lng)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "day_of_year": now.timetuple().tm_yday,
        "season": _season(now.month),
        "location": {"lat": lat, "lng": lng},
        "node_name": node_name,
        "weather": weather,
    }
