"""
Ajax Systems Cloud API integration.
Docs: https://api.ajax.systems/swagger-ui
Access request: https://ajax.systems/api-request/

Required env vars:
  AJAX_EMAIL    — Ajax account email
  AJAX_PASSWORD — Ajax account password

Polls all hubs and their device states, writes to SensorReading table.

Device types mapped:
  DoorProtect / DoorProtect Plus  → "door"
  MotionProtect                   → "motion"
  LeaksProtect                    → "leak"
  FireProtect                     → "fire"
  Rex / range extenders           → skipped
  Fence zones / GPIO              → "fence"
"""
import uuid
import json
import requests
from app.config import settings

BASE = "https://api.ajax.systems"

DOOR_TYPES = {"DoorProtect", "DoorProtectPlus", "DoorProtectPlusJeweller"}
MOTION_TYPES = {"MotionProtect", "MotionProtectPlus", "MotionCam"}
FENCE_TYPES = {"WallSwitch", "Socket", "Relay"}


def _get_token() -> str | None:
    if not settings.ajax_email or not settings.ajax_password:
        return None
    try:
        r = requests.post(
            f"{BASE}/login",
            json={"email": settings.ajax_email, "password": settings.ajax_password},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        return data.get("sessionToken") or data.get("accessToken")
    except Exception:
        return None


def _device_type(device: dict) -> str | None:
    model = device.get("model", "")
    if any(t in model for t in DOOR_TYPES):
        return "door"
    if any(t in model for t in MOTION_TYPES):
        return "motion"
    if any(t in model for t in FENCE_TYPES):
        return "fence"
    if "FireProtect" in model:
        return "fire"
    if "LeaksProtect" in model:
        return "leak"
    return None


def _device_status(device: dict) -> str:
    state = device.get("state", {})
    if state.get("triggered") or state.get("alarm"):
        return "triggered"
    if state.get("open") is True:
        return "open"
    if state.get("open") is False:
        return "closed"
    return state.get("status", "ok")


def sync(node_id: str, db) -> int:
    """
    Fetch all device states from Ajax Cloud and write to SensorReading.
    Returns number of readings recorded.
    """
    from app.models.sensor_reading import SensorReading

    token = _get_token()
    if not token:
        return 0

    recorded = 0
    try:
        hubs = requests.get(
            f"{BASE}/hubs",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        ).json().get("data", [])

        for hub in hubs:
            hub_id = hub.get("id")
            devices = requests.get(
                f"{BASE}/hubs/{hub_id}/devices",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            ).json().get("data", [])

            for device in devices:
                sensor_type = _device_type(device)
                if not sensor_type:
                    continue
                status = _device_status(device)
                db.add(SensorReading(
                    id=str(uuid.uuid4()),
                    node_id=node_id,
                    source="ajax",
                    sensor_type=sensor_type,
                    device_id=device.get("id"),
                    device_name=device.get("name"),
                    value=None,
                    unit=None,
                    status=status,
                    data_json=json.dumps(device),
                ))
                recorded += 1
    except Exception:
        pass

    db.commit()
    return recorded
