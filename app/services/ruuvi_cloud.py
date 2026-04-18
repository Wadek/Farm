"""
Ruuvi Cloud API integration.
Docs: https://docs.ruuvi.com/communicate-with-ruuvi-cloud/cloud/user-api

Required env vars:
  RUUVI_EMAIL    — your ruuvi.com account email
  RUUVI_PASSWORD — your ruuvi.com account password

Polls sensor list and latest measurements, writes to SensorReading table.
"""
import uuid
import json
import requests
from app.config import settings

BASE = "https://network.ruuvi.com"


def _get_token() -> str | None:
    if not settings.ruuvi_email or not settings.ruuvi_password:
        return None
    try:
        r = requests.post(
            f"{BASE}/user/login",
            json={"email": settings.ruuvi_email, "password": settings.ruuvi_password},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("data", {}).get("accessToken")
    except Exception:
        return None


def fetch_sensors(token: str) -> list[dict]:
    try:
        r = requests.get(
            f"{BASE}/sensors-dense",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("data", {}).get("sensors", [])
    except Exception:
        return []


def sync(node_id: str, db) -> int:
    """
    Fetch latest readings from all Ruuvi Cloud sensors and write to SensorReading.
    Returns number of readings recorded.
    """
    from app.models.sensor_reading import SensorReading

    token = _get_token()
    if not token:
        return 0

    sensors = fetch_sensors(token)
    recorded = 0

    for sensor in sensors:
        mac = sensor.get("sensor")
        measurements = sensor.get("measurements", [])
        if not measurements:
            continue
        m = measurements[-1]  # latest

        temp = m.get("temperature")
        humidity = m.get("humidity")
        pressure = m.get("pressure")
        battery = m.get("voltage")

        for sensor_type, value, unit in [
            ("temperature", temp, "°C"),
            ("humidity", humidity, "%"),
            ("pressure", pressure, "hPa"),
            ("battery", battery, "V"),
        ]:
            if value is None:
                continue
            db.add(SensorReading(
                id=str(uuid.uuid4()),
                node_id=node_id,
                source="ruuvi",
                sensor_type=sensor_type,
                device_id=mac,
                device_name=sensor.get("name") or mac,
                value=value,
                unit=unit,
                status=None,
                data_json=json.dumps(m),
            ))
            recorded += 1

    db.commit()
    return recorded
