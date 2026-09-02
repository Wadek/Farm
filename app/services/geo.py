import math

import requests


EARTH_RADIUS_KM = 6371.0
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA = "Satokori/1.0 (https://satokori.com; satokori@wakalabs.net)"


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance in km between two GPS coordinates."""
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def geocode_fi(query: str) -> dict | None:
    """Resolve a Finnish address to lat/lng via Nominatim. None if no hit."""
    q = " ".join((query or "").split())
    if len(q) < 3:
        return None
    r = requests.get(
        NOMINATIM_URL,
        params={
            "q": q,
            "format": "json",
            "limit": 1,
            "countrycodes": "fi",
        },
        headers={"User-Agent": NOMINATIM_UA, "Accept-Language": "fi,en"},
        timeout=8,
    )
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list) or not rows:
        return None
    hit = rows[0]
    return {
        "lat": float(hit["lat"]),
        "lng": float(hit["lon"]),
        "label": hit.get("display_name") or q,
        "query": q,
    }
