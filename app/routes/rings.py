"""REKO rings: shared drop place and time. Customers pre-order; pay at the lot."""

import secrets
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.db import get_db
from app.models import Listing, ListingStatus, Node, Ring, RingDrop, User, UserRole
from app.models.ask import PickupAsk, AskStatus
from app.dependencies import get_current_user, require_organizer
from app.routes.produce import _listing_view
from app.routes.square import _iso

router = APIRouter(tags=["rings"])


class RingIn(BaseModel):
    name: str
    place: str
    lat: float
    lng: float
    notes: str = ""
    facebook_url: str = ""
    starts_at: datetime
    ends_at: datetime
    order_until: datetime | None = None


class DropIn(BaseModel):
    starts_at: datetime
    ends_at: datetime
    order_until: datetime | None = None


class AttendIn(BaseModel):
    going: bool
    node_id: str


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _can_manage(user: User, ring: Ring) -> bool:
    if user.role == UserRole.organizer:
        return True
    return bool(ring.admin_id and ring.admin_id == user.id)


def _ring_public(r: Ring) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "place": r.place,
        "lat": r.lat,
        "lng": r.lng,
        "notes": r.notes or "",
        "facebook_url": r.facebook_url or "",
        "is_unclaimed": r.claimed_at is None,
        "admin_name": r.admin.name if r.admin else "",
        "claim_id": r.claim_id,
    }


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
        .options(joinedload(Ring.admin))
        .order_by(Ring.created_at.desc())
        .all()
    )
    return {
        "rings": [_ring_public(r) for r in rings],
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
        facebook_url=payload.facebook_url.strip(),
        claim_id=secrets.token_urlsafe(10),
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


@router.post("/rings/{ring_id}/claim")
def claim_ring(
    ring_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in (UserRole.ring_admin, UserRole.farmer, UserRole.organizer):
        raise HTTPException(status_code=403, detail="Only ring admins can claim a ring")
    ring = db.query(Ring).options(joinedload(Ring.admin)).filter(Ring.id == ring_id).first()
    if not ring:
        raise HTTPException(status_code=404, detail="Ring not found")
    if ring.claimed_at:
        raise HTTPException(status_code=409, detail="Ring is already claimed")
    ring.admin_id = current_user.id
    ring.claimed_at = _now()
    db.commit()
    db.refresh(ring)
    return _ring_public(ring)


@router.post("/rings/{ring_id}/drops", status_code=201)
def create_drop(
    ring_id: str,
    payload: DropIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ring = db.query(Ring).filter(Ring.id == ring_id).first()
    if not ring:
        raise HTTPException(status_code=404, detail="Ring not found")
    if not _can_manage(current_user, ring):
        raise HTTPException(status_code=403, detail="Ring admins only")
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail="Drop must end after it starts")
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


def _owned_node(node_id: str, user: User, db: Session) -> Node:
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Farm not found")
    if node.owner_id != user.id and user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Not your farm")
    return node


@router.post("/drops/{drop_id}/attend")
def attend_drop(
    drop_id: str,
    payload: AttendIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in (UserRole.farmer, UserRole.organizer):
        raise HTTPException(status_code=403, detail="Farmers only")
    node = _owned_node(payload.node_id, current_user, db)
    drop = (
        db.query(RingDrop)
        .options(joinedload(RingDrop.ring))
        .filter(RingDrop.id == drop_id)
        .first()
    )
    if not drop:
        raise HTTPException(status_code=404, detail="Drop not found")
    drop_lots = (
        db.query(Listing)
        .options(joinedload(Listing.produce))
        .filter(Listing.node_id == node.id, Listing.drop_id == drop.id)
        .all()
    )
    if not payload.going:
        ids = [lot.id for lot in drop_lots]
        if ids:
            open_asks = (
                db.query(PickupAsk)
                .filter(
                    PickupAsk.listing_id.in_(ids),
                    PickupAsk.status.in_((AskStatus.asked, AskStatus.confirmed, AskStatus.offered)),
                )
                .count()
            )
            if open_asks:
                raise HTTPException(
                    status_code=409,
                    detail="Customers already ordered — reply in Orders first",
                )
        for lot in drop_lots:
            lot.status = ListingStatus.completed
        db.commit()
        return {"going": False, "drop_id": drop.id, "lot_count": 0}

    gate_lots = (
        db.query(Listing)
        .options(joinedload(Listing.produce))
        .filter(
            Listing.node_id == node.id,
            Listing.drop_id.is_(None),
            Listing.status == ListingStatus.active,
        )
        .all()
    )
    by_produce = {lot.produce_id: lot for lot in drop_lots}
    place = drop.ring.place if drop.ring else (node.description or node.name)
    for src in gate_lots:
        existing = by_produce.get(src.produce_id)
        if existing:
            existing.status = ListingStatus.active
            existing.quantity_kg = src.quantity_kg
            existing.price_per_kg = src.price_per_kg
            existing.unit = src.unit or "kg"
            existing.pickup_point = place
            existing.available_from = drop.starts_at
            existing.available_until = drop.ends_at
            existing.perpetual = False
            continue
        clone = Listing(
            id=str(uuid.uuid4()),
            node_id=node.id,
            produce_id=src.produce_id,
            quantity_kg=src.quantity_kg,
            unit=src.unit or "kg",
            price_per_kg=src.price_per_kg,
            pickup_point=place,
            is_free=src.is_free,
            available_from=drop.starts_at,
            available_until=drop.ends_at,
            perpetual=False,
            demo=bool(src.demo),
            drop_id=drop.id,
            image_url=src.image_url,
            private=bool(src.private),
            privacy_v=src.privacy_v,
            privacy_iv=src.privacy_iv,
            privacy_ct=src.privacy_ct,
            status=ListingStatus.active,
        )
        db.add(clone)
        by_produce[src.produce_id] = clone
    db.flush()
    active = [lot for lot in by_produce.values() if lot.status == ListingStatus.active]
    if not active:
        raise HTTPException(status_code=400, detail="List something at the farm first")
    db.commit()
    return {"going": True, "drop_id": drop.id, "lot_count": len(active)}
