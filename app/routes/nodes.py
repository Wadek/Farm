import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Node, NodeType
from app.models.ruuvi_reading import RuuviReading
from app.models.user import User
from app.dependencies import get_current_user

router = APIRouter(prefix="/nodes", tags=["nodes"])


class NodeCreate(BaseModel):
    name: str
    type: NodeType
    lat: float
    lng: float
    description: str = ""
    area_m2: float = 0.0


class RuuviPost(BaseModel):
    mac: str | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    pressure_hpa: float | None = None
    battery_v: float | None = None
    rssi: int | None = None


@router.post("", status_code=201)
def create_node(payload: NodeCreate, current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    node = Node(
        id=str(uuid.uuid4()),
        owner_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


@router.get("")
def list_nodes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    nodes = db.query(Node).filter(Node.owner_id == current_user.id).all()
    return [_node_view(n, db) for n in nodes]


@router.get("/{node_id}")
def get_node(node_id: str, current_user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return _node_view(node, db)


@router.post("/{node_id}/ruuvi", status_code=201)
def post_ruuvi(node_id: str, payload: RuuviPost, db: Session = Depends(get_db)):
    """Accepts Ruuvi sensor readings — callable from desktop BLE script or phone."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    reading = RuuviReading(id=str(uuid.uuid4()), node_id=node_id, **payload.model_dump())
    db.add(reading)
    db.commit()
    return {"status": "recorded"}


@router.get("/{node_id}/ruuvi/latest")
def latest_ruuvi(node_id: str, db: Session = Depends(get_db)):
    reading = (
        db.query(RuuviReading)
        .filter(RuuviReading.node_id == node_id)
        .order_by(RuuviReading.recorded_at.desc())
        .first()
    )
    if not reading:
        return {"status": "no data"}
    return {
        "temperature_c": reading.temperature_c,
        "humidity_pct": reading.humidity_pct,
        "pressure_hpa": reading.pressure_hpa,
        "battery_v": reading.battery_v,
        "rssi": reading.rssi,
        "mac": reading.mac,
        "recorded_at": reading.recorded_at.isoformat() if reading.recorded_at else None,
    }


@router.post("/ruuvi/webhook")
def ruuvi_station_webhook(payload: dict[str, Any], db: Session = Depends(get_db)):
    """
    Accepts Ruuvi Station iOS app data forwarding webhook.
    Maps sensor MAC addresses to nodes automatically.
    Configure in Ruuvi Station: Settings → Data forwarding → URL → http://<chromebook-ip>:8000/nodes/ruuvi/webhook
    """
    recorded = 0
    tags = payload.get("tags", [])
    for tag in tags:
        mac = tag.get("id") or tag.get("mac")
        if not mac:
            continue
        node = db.query(Node).filter(Node.ruuvi_mac == mac).first() if hasattr(Node, 'ruuvi_mac') else None
        # Fall back: find any node — single-node setup
        if not node:
            node = db.query(Node).order_by(Node.created_at).first()
        if not node:
            continue
        reading = RuuviReading(
            id=str(uuid.uuid4()),
            node_id=node.id,
            mac=mac,
            temperature_c=tag.get("temperature"),
            humidity_pct=tag.get("humidity"),
            pressure_hpa=tag.get("pressure"),
            battery_v=tag.get("voltage") or tag.get("battery"),
            rssi=tag.get("rssi"),
        )
        db.add(reading)
        recorded += 1
    db.commit()
    return {"recorded": recorded}


def _node_view(node: Node, db: Session) -> dict:
    latest = (
        db.query(RuuviReading)
        .filter(RuuviReading.node_id == node.id)
        .order_by(RuuviReading.recorded_at.desc())
        .first()
    )
    return {
        "id": node.id,
        "name": node.name,
        "type": node.type,
        "lat": node.lat,
        "lng": node.lng,
        "area_m2": node.area_m2,
        "description": node.description,
        "myc_tokens": round(node.myc_tokens, 4),
        "ruuvi": {
            "temperature_c": latest.temperature_c if latest else None,
            "humidity_pct": latest.humidity_pct if latest else None,
            "pressure_hpa": latest.pressure_hpa if latest else None,
            "battery_v": latest.battery_v if latest else None,
            "recorded_at": latest.recorded_at.isoformat() if latest else None,
        } if latest else None,
    }
