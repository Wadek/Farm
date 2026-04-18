from unittest.mock import patch, MagicMock
from app.services.regional_service import detect_country, fetch_constants, _fi_current_spot_price
from app.services.token_engine import calculate, constants_from_regional, RegionalConstants


# --- country detection ---

def test_detect_finland():
    assert detect_country(60.5522, 24.7050) == "FI"


def test_detect_hyvinkaa():
    assert detect_country(60.63, 24.86) == "FI"


def test_detect_unknown():
    assert detect_country(0.0, 0.0) == "UNKNOWN"


def test_detect_sweden():
    assert detect_country(59.33, 18.06) == "SE"


# --- PorssisÃ¤hkö spot price parsing ---

def test_spot_price_parsed():
    import datetime
    mock_now = datetime.datetime(2026, 4, 18, 18, 30, 0, tzinfo=datetime.timezone.utc)
    mock_prices = {
        "prices": [
            {"price": 5.5, "startDate": "2026-04-18T18:00:00.000Z", "endDate": "2026-04-18T19:00:00.000Z"},
            {"price": 3.2, "startDate": "2026-04-18T17:00:00.000Z", "endDate": "2026-04-18T18:00:00.000Z"},
        ]
    }
    with patch("app.services.regional_service.requests.get") as mock_get, \
         patch("app.services.regional_service.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = mock_now
        mock_dt.timezone = datetime.timezone
        mock_dt.datetime.fromisoformat = datetime.datetime.fromisoformat
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_prices
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        price = _fi_current_spot_price()
    # 18:30 UTC falls in 18:00–19:00 slot → 5.5 c/kWh → €0.055
    assert price == 5.5 / 100.0


def test_spot_price_api_failure_returns_none():
    with patch("app.services.regional_service.requests.get", side_effect=Exception("timeout")):
        price = _fi_current_spot_price()
    assert price is None


# --- fetch_constants ---

def test_fetch_fi_constants():
    with patch("app.services.regional_service._fi_current_spot_price", return_value=0.045), \
         patch("app.services.regional_service._fi_weekly_avg_price", return_value=0.052):
        c = fetch_constants(60.5522, 24.7050)
    assert c.country_code == "FI"
    assert c.kwh_price_eur == 0.045
    assert c.kwh_weekly_avg_eur == 0.052
    assert c.grid_intensity == 0.038
    assert c.import_distance_km == 2500.0
    assert "PLACEHOLDER" in c.source_notes


def test_fetch_unsupported_country_raises():
    import pytest
    with pytest.raises(NotImplementedError):
        fetch_constants(51.5, -0.1)  # London


# --- token engine with dynamic constants ---

def test_token_engine_uses_regional_constants():
    high_price = RegionalConstants(
        kwh_price_eur=0.30,
        carbon_value_eur_per_kg=0.10,
        import_distance_km=2500.0,
        store_transport_factor=0.00015,
        local_transport_factor=0.00005,
    )
    low_price = RegionalConstants(
        kwh_price_eur=0.03,
        carbon_value_eur_per_kg=0.05,
        import_distance_km=2500.0,
        store_transport_factor=0.00015,
        local_transport_factor=0.00005,
    )
    result_high = calculate(180.0, 2.5, 0.4, 1.0, 1.0, True, constants=high_price)
    result_low = calculate(180.0, 2.5, 0.4, 1.0, 1.0, True, constants=low_price)
    assert result_high.myc_tokens > result_low.myc_tokens


def test_constants_from_regional_record():
    mock_record = MagicMock()
    mock_record.kwh_spot_eur = 0.045
    mock_record.carbon_value_eur_per_kg = 0.065
    mock_record.import_distance_km = 2500.0
    mock_record.store_transport_factor = 0.00015
    mock_record.local_transport_factor = 0.00005

    c = constants_from_regional(mock_record)
    assert c.kwh_price_eur == 0.045
    assert c.carbon_value_eur_per_kg == 0.065


# --- weekly cache logic ---

def test_get_or_refresh_uses_cache(db):
    from app.services.regional_service import get_or_refresh
    import datetime

    with patch("app.services.regional_service._fi_current_spot_price", return_value=0.04), \
         patch("app.services.regional_service._fi_weekly_avg_price", return_value=0.05):
        first = get_or_refresh(60.5522, 24.7050, db)
        second = get_or_refresh(60.5522, 24.7050, db)

    assert first.id == second.id  # same cached record returned


def test_get_or_refresh_writes_new_record(db):
    from app.models.regional_config import RegionalConfig
    from app.services.regional_service import get_or_refresh

    with patch("app.services.regional_service._fi_current_spot_price", return_value=0.04), \
         patch("app.services.regional_service._fi_weekly_avg_price", return_value=0.05):
        get_or_refresh(60.5522, 24.7050, db)

    count = db.query(RegionalConfig).count()
    assert count == 1
