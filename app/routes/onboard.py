"""Field-visit onboarding — Wade adds a farm in one sitting."""

import re
import secrets
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Node, NodeType, Produce, Listing, ListingStatus, User, UserRole
from app.dependencies import require_organizer
from app.services.auth_service import hash_password
from app.routes.produce import _listing_view
from app.routes.square import LotIn, _iso

router = APIRouter(tags=["onboard"])


class FarmOnboard(BaseModel):
    farmer_name: str
    farm_name: str
    pickup_point: str
    lat: float
    lng: float
    phone: str = ""
    email: str | None = None
    password: str | None = None
    node_type: NodeType = NodeType.hobby_farm
    notes: str = ""
    available_from: datetime | None = None
    available_until: datetime | None = None
    lots: list[LotIn] = []


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "tila"


@router.post("/onboard", status_code=201)
def onboard_farm(
    payload: FarmOnboard,
    organizer: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    """Create farmer + node + first table in one visit. Password is returned once."""
    password = payload.password or secrets.token_urlsafe(6)
    email = (payload.email or f"{_slug(payload.farm_name)}@satokori.local").lower()
    if db.query(User).filter(User.email == email).first():
        email = f"{_slug(payload.farm_name)}-{secrets.token_hex(2)}@satokori.local"

    farmer = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=hash_password(password),
        name=payload.farmer_name,
        role=UserRole.farmer,
        phone=payload.phone,
    )
    db.add(farmer)
    db.flush()

    node = Node(
        id=str(uuid.uuid4()),
        owner_id=farmer.id,
        name=payload.farm_name,
        type=payload.node_type,
        lat=payload.lat,
        lng=payload.lng,
        description=payload.notes or payload.pickup_point,
        area_m2=0.0,
    )
    db.add(node)
    db.flush()

    created = []
    if payload.lots:
        if not payload.available_from or not payload.available_until:
            raise HTTPException(status_code=400, detail="Lots need a pickup window")
        for lot in payload.lots:
            produce = Produce(
                id=str(uuid.uuid4()),
                node_id=node.id,
                name=lot.produce_name,
                category=lot.category,
                quantity_kg=lot.quantity_kg,
                kcal_per_kg=lot.kcal_per_kg,
                co2_kg_per_kg=lot.co2_kg_per_kg,
            )
            db.add(produce)
            db.flush()
            listing = Listing(
                id=str(uuid.uuid4()),
                node_id=node.id,
                produce_id=produce.id,
                quantity_kg=lot.quantity_kg,
                price_per_kg=lot.price_per_kg,
                pickup_point=payload.pickup_point,
                is_free=lot.is_free or lot.price_per_kg == 0,
                available_from=payload.available_from,
                available_until=payload.available_until,
                status=ListingStatus.active,
            )
            db.add(listing)
            created.append(listing)

    db.commit()
    for listing in created:
        db.refresh(listing)

    return {
        "farm_name": node.name,
        "farmer_name": farmer.name,
        "email": farmer.email,
        "password": password,
        "phone": farmer.phone,
        "node_id": node.id,
        "pickup_point": payload.pickup_point,
        "available_from": _iso(payload.available_from),
        "available_until": _iso(payload.available_until),
        "lots": [_listing_view(l) for l in created],
        "note": "Write the login on paper. This app is a chalkboard, not a till.",
    }
