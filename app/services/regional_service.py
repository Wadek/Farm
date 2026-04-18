"""
Regional constants service — fetches and caches weekly regional data
used by the token engine. Designed for multi-country future expansion;
currently implements Finland only.

Data sources:
  - Electricity spot price: api.porssisahko.net (Finland, Nordpool day-ahead)
  - Grid carbon intensity:  Fingrid/Our World in Data annual average (static, FI)
  - EU ETS carbon price:    Placeholder — future API integration needed
  - Supply chain constants: Placeholder — future supply chain data engine needed

Refresh cadence: once per week (168 hours). On each token calculation the
service returns the cached config if still valid, or fetches fresh data.
"""
import uuid
import datetime
import requests
from dataclasses import dataclass

REFRESH_INTERVAL_HOURS = 168  # one week

# Finland defaults — used as fallback if fetch fails
# Grid intensity: Finland 2024 average ~0.038 kg CO2/kWh (nuclear + hydro heavy grid)
# Carbon value:   EU ETS ~€65/tonne as of early 2026 = €0.065/kg
# Supply chain:   PLACEHOLDER — arbitrary, needs supply chain data engine
_FI_DEFAULTS = {
    "grid_intensity_kg_co2_per_kwh": 0.038,
    "carbon_value_eur_per_kg": 0.065,
    "import_distance_km": 2500.0,       # PLACEHOLDER: avg Finland food import distance
    "store_transport_factor": 0.00015,  # PLACEHOLDER: kg CO2 per km per kg (industrial)
    "local_transport_factor": 0.00005,  # PLACEHOLDER: kg CO2 per km per kg (local vehicle)
}

# Bounding boxes for country detection — expand as new regions are added
_COUNTRY_BOUNDS = {
    "FI": {"lat": (59.5, 70.1), "lng": (19.0, 31.6)},
    "SE": {"lat": (55.0, 69.1), "lng": (10.5, 24.2)},
    "NO": {"lat": (57.0, 71.2), "lng": (4.0, 31.3)},
}


@dataclass
class RegionalConstants:
    country_code: str
    kwh_price_eur: float
    kwh_weekly_avg_eur: float
    grid_intensity: float
    carbon_value_eur_per_kg: float
    import_distance_km: float
    store_transport_factor: float
    local_transport_factor: float
    source_notes: str


def detect_country(lat: float, lng: float) -> str:
    for code, bounds in _COUNTRY_BOUNDS.items():
        if bounds["lat"][0] <= lat <= bounds["lat"][1]:
            if bounds["lng"][0] <= lng <= bounds["lng"][1]:
                return code
    return "UNKNOWN"


def _fi_current_spot_price() -> float | None:
    """Fetch current hourly spot price from PorssisÃ¤hkö (c/kWh → €/kWh)."""
    try:
        r = requests.get("https://api.porssisahko.net/v1/latest-prices.json", timeout=5)
        r.raise_for_status()
        prices = r.json().get("prices", [])
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for entry in prices:
            start = datetime.datetime.fromisoformat(entry["startDate"].replace("Z", "+00:00"))
            end = datetime.datetime.fromisoformat(entry["endDate"].replace("Z", "+00:00"))
            if start <= now_utc < end:
                return entry["price"] / 100.0  # c/kWh → €/kWh
    except Exception:
        pass
    return None


def _fi_weekly_avg_price() -> float | None:
    """Fetch 7-day average electricity price from PorssisÃ¤hkö."""
    try:
        prices = []
        today = datetime.date.today()
        for offset in range(7):
            day = today - datetime.timedelta(days=offset)
            r = requests.get(
                f"https://api.porssisahko.net/v1/price.json?date={day.isoformat()}",
                timeout=5,
            )
            if r.ok:
                for entry in r.json().get("prices", []):
                    prices.append(entry["price"])
        if prices:
            return (sum(prices) / len(prices)) / 100.0  # c/kWh → €/kWh
    except Exception:
        pass
    return None


def _build_fi_constants() -> tuple[RegionalConstants, str]:
    notes = []
    spot = _fi_current_spot_price()
    if spot is not None:
        notes.append("electricity_spot:porssisahko")
    else:
        spot = 0.12  # reasonable Finland fallback if API unavailable
        notes.append("electricity_spot:fallback(0.12)")

    weekly_avg = _fi_weekly_avg_price()
    if weekly_avg is not None:
        notes.append("electricity_weekly_avg:porssisahko")
    else:
        weekly_avg = spot
        notes.append("electricity_weekly_avg:fallback(spot)")

    notes.append("grid_intensity:fingrid_annual_2024")
    notes.append("carbon_value:eu_ets_estimate_2026")
    notes.append("supply_chain:PLACEHOLDER_needs_engine")

    return RegionalConstants(
        country_code="FI",
        kwh_price_eur=spot,
        kwh_weekly_avg_eur=weekly_avg,
        grid_intensity=_FI_DEFAULTS["grid_intensity_kg_co2_per_kwh"],
        carbon_value_eur_per_kg=_FI_DEFAULTS["carbon_value_eur_per_kg"],
        import_distance_km=_FI_DEFAULTS["import_distance_km"],
        store_transport_factor=_FI_DEFAULTS["store_transport_factor"],
        local_transport_factor=_FI_DEFAULTS["local_transport_factor"],
        source_notes="; ".join(notes),
    ), "; ".join(notes)


def fetch_constants(lat: float, lng: float) -> RegionalConstants:
    """
    Fetch regional constants for the given coordinates.
    Raises NotImplementedError for countries without an implementation yet.
    """
    country = detect_country(lat, lng)
    if country == "FI":
        constants, _ = _build_fi_constants()
        return constants
    raise NotImplementedError(
        f"Regional constants not yet implemented for country: {country}. "
        "Only Finland (FI) is currently supported."
    )


def get_or_refresh(lat: float, lng: float, db) -> "RegionalConfig":
    """
    Return a valid cached RegionalConfig from DB, or fetch fresh if expired.
    Writes new rows (append-only) — never updates existing records.
    """
    from app.models.regional_config import RegionalConfig

    now = datetime.datetime.utcnow()
    country = detect_country(lat, lng)

    cached = (
        db.query(RegionalConfig)
        .filter(
            RegionalConfig.country_code == country,
            RegionalConfig.valid_until > now,
        )
        .order_by(RegionalConfig.fetched_at.desc())
        .first()
    )
    if cached:
        return cached

    constants = fetch_constants(lat, lng)

    record = RegionalConfig(
        id=str(uuid.uuid4()),
        country_code=constants.country_code,
        region=None,
        lat=lat,
        lng=lng,
        kwh_spot_eur=constants.kwh_price_eur,
        kwh_weekly_avg_eur=constants.kwh_weekly_avg_eur,
        grid_intensity_kg_co2_per_kwh=constants.grid_intensity,
        carbon_value_eur_per_kg=constants.carbon_value_eur_per_kg,
        import_distance_km=constants.import_distance_km,
        store_transport_factor=constants.store_transport_factor,
        local_transport_factor=constants.local_transport_factor,
        fetched_at=now,
        valid_until=now + datetime.timedelta(hours=REFRESH_INTERVAL_HOURS),
        source_notes=constants.source_notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
