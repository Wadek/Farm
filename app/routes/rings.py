"""REKO rings: shared drop place and time. Customers pre-order; pay at the lot."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.db import get_db
from app.models import Listing, ListingStatus, Ring, RingDrop, User, UserRole
from app.dependencies import require_organizer
from app.routes.produce import _listing_view
from app.routes.square import _iso

router = APIRouter(tags=["rings"])


class RingIn(BaseModel):
    name: str
    place: str
    lat: float
    lng: float
    notes: str = ""
    starts_at: datetime
    ends_at: datetime
    order_until: datetime | None = None


def _drop_public(drop: RingDrop, include_offers: bool = True) -> dict:
    ring = drop.ring
    offers = []
    if include_offers:
        for listing in drop.listings or []:
            if listing.status in (ListingStatus.active, ListingStatus.sold_out):
                offers.append(_listing_view(listing))
    return {
        "id": drop.id,
        "ring_id": drop.ring_id,
        "ring_name": ring.name if ring else "",
        "place": ring.place if ring else "",
        "lat": ring.lat if ring else None,
        "lng": ring.lng if ring else None,
        "notes": (ring.notes if ring else "") or "",
        "starts_at": _iso(drop.starts_at),
        "ends_at": _iso(drop.ends_at),
        "order_until": _iso(drop.order_until),
        "offers": offers,
        "offer_count": len(offers),
    }


@router.get("/rings")
def list_rings(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    drops = (
        db.query(RingDrop)
        .options(
            joinedload(RingDrop.ring),
            joinedload(RingDrop.listings).joinedload(Listing.produce),
            joinedload(RingDrop.listings).joinedload(Listing.node),
        )
        .filter(RingDrop.ends_at >= now)
        .order_by(RingDrop.starts_at.asc())
        .all()
    )
    rings = (
        db.query(Ring)
        .order_by(Ring.created_at.desc())
        .all()
    )
    return {
        "rings": [
            {
                "id": r.id,
                "name": r.name,
                "place": r.place,
                "lat": r.lat,
                "lng": r.lng,
                "notes": r.notes or "",
            }
            for r in rings
        ],
        "drops": [_drop_public(d) for d in drops],
        "next_drop": _drop_public(drops[0]) if drops else None,
    }


@router.post("/rings", status_code=201)
def create_ring(
    payload: RingIn,
    organizer: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail="Drop must end after it starts")
    ring = Ring(
        id=str(uuid.uuid4()),
        name=payload.name.strip(),
        place=payload.place.strip(),
        lat=payload.lat,
        lng=payload.lng,
        notes=payload.notes.strip(),
    )
    db.add(ring)
    db.flush()
    drop = RingDrop(
        id=str(uuid.uuid4()),
        ring_id=ring.id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        order_until=payload.order_until or payload.starts_at,
    )
    db.add(drop)
    db.commit()
    db.refresh(drop)
    drop = (
        db.query(RingDrop)
        .options(joinedload(RingDrop.ring), joinedload(RingDrop.listings))
        .filter(RingDrop.id == drop.id)
        .first()
    )
    return _drop_public(drop)
