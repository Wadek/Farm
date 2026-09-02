"""Organizer dashboard: farms, featured listing, counts."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.db import get_db
import uuid
from datetime import datetime, timezone
from app.models import Node, Listing, ListingStatus, User, UserRole
from app.models.message import Message
from app.models.ask import PickupAsk
from app.dependencies import require_organizer
from app.routes.produce import _listing_view
from app.routes.square import _iso
from app.services.privacy import admin_farm_view, admin_listing_view

router = APIRouter(prefix="/admin", tags=["admin"])


class FeatureIn(BaseModel):
    listing_id: str | None = None


class ClaimDecision(BaseModel):
    node_id: str
    approve: bool = True


def _farm_row(node: Node, listings: list[Listing]) -> dict:
    claimed = node.claimed_at is not None
    owner = node.owner
    owner_private = bool(owner and getattr(owner, "privacy", False))
    last_listing = max((l.created_at for l in listings if l.created_at), default=None)
    last_sync = getattr(owner, "last_sync_at", None) if owner else None
    raw = {
        "id": node.id,
        "name": node.name,
        "type": node.type.value if node.type else "farm",
        "lat": node.lat,
        "lng": node.lng,
        "description": node.description or "",
        "claim_id": node.claim_id,
        "claimed_at": _iso(node.claimed_at),
        "is_unclaimed": not claimed,
        "created_at": _iso(node.created_at),
        "owner_id": owner.id if claimed and owner else "",
        "owner_name": owner.name if claimed and owner else "",
        "owner_email": owner.email if claimed and owner else "",
        "owner_phone": owner.phone if claimed and owner else "",
        "owner_disabled": bool(getattr(owner, "disabled", False)) if owner else False,
        "last_sync_at": _iso(last_sync or last_listing),
        "claim_pending": bool(node.claim_pending_user_id) and not claimed,
        "claim_pending_user_id": node.claim_pending_user_id or "",
        "claim_pending_name": node.claim_pending_user.name if node.claim_pending_user else "",
        "claim_pending_email": node.claim_pending_user.email if node.claim_pending_user else "",
        "listing_count": len(listings),
        "demo_count": sum(1 for l in listings if getattr(l, "demo", False)),
        "listings": [_listing_view(l) for l in listings],
    }
    return admin_farm_view(raw, owner_private)


@router.get("/overview")
def admin_overview(
    organizer: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    nodes = (
        db.query(Node)
        .options(joinedload(Node.owner), joinedload(Node.claim_pending_user))
        .order_by(Node.created_at.desc())
        .all()
    )
    listings = (
        db.query(Listing)
        .options(joinedload(Listing.produce), joinedload(Listing.node).joinedload(Node.owner))
        .order_by(Listing.created_at.desc())
        .all()
    )
    by_node: dict[str, list[Listing]] = {n.id: [] for n in nodes}
    featured = None
    for listing in listings:
        by_node.setdefault(listing.node_id, []).append(listing)
        if getattr(listing, "featured", False) and featured is None:
            featured = _listing_view(listing)
    farms = [_farm_row(n, by_node.get(n.id, [])) for n in nodes]
    asks = db.query(PickupAsk).count()
    public_listings = []
    for listing in listings:
        view = _listing_view(listing)
        owner = listing.node.owner if listing.node else None
        if getattr(listing, "private", False) or (owner and getattr(owner, "privacy", False)):
            public_listings.append(admin_listing_view(view))
        else:
            view.pop("lockbox", None)
            public_listings.append(view)
    if featured and featured.get("private"):
        featured = admin_listing_view(featured)
    private_count = sum(1 for f in farms if f.get("private"))
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    def _parse(ts):
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    active = sum(1 for f in farms if (dt := _parse(f.get("last_sync_at"))) and dt >= cutoff)
    return {
        "farm_count": len(farms),
        "unclaimed_count": sum(1 for f in farms if f["is_unclaimed"]),
        "listing_count": len(listings),
        "demo_count": sum(1 for l in listings if getattr(l, "demo", False)),
        "ask_count": asks,
        "private_count": private_count,
        "active_count": active,
        "featured": featured,
        "pending_claims": [f for f in farms if f["claim_pending"]],
        "farms": farms,
        "listings": public_listings,
    }


@router.post("/claims")
def decide_claim(
    payload: ClaimDecision,
    organizer: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    node = (
        db.query(Node)
        .options(joinedload(Node.claim_pending_user))
        .filter(Node.id == payload.node_id)
        .first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="Farm not found")
    if node.claimed_at:
        raise HTTPException(status_code=409, detail="Farm has already been claimed")
    if not node.claim_pending_user_id:
        raise HTTPException(status_code=409, detail="No pending claim")
    farmer = node.claim_pending_user
    farmer_id = node.claim_pending_user_id
    now = datetime.now(timezone.utc)
    if payload.approve:
        node.owner_id = farmer_id
        node.claimed_at = now
        node.claim_pending_user_id = None
        node.claim_pending_at = None
        body = f"Admin approved your claim of {node.name}."
    else:
        node.claim_pending_user_id = None
        node.claim_pending_at = None
        body = f"Admin declined your claim of {node.name}."
    if farmer:
        db.add(Message(
            id=str(uuid.uuid4()),
            sender_id=organizer.id,
            recipient_id=farmer_id,
            listing_id=None,
            body=body,
        ))
    db.commit()
    return {"node_id": node.id, "farm_name": node.name, "status": "claimed" if payload.approve else "declined"}


@router.post("/featured")
def set_featured(
    payload: FeatureIn,
    organizer: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    chosen = None
    if payload.listing_id:
        chosen = (
            db.query(Listing)
            .options(joinedload(Listing.produce), joinedload(Listing.node).joinedload(Node.owner))
            .filter(Listing.id == payload.listing_id)
            .first()
        )
        if not chosen:
            raise HTTPException(status_code=404, detail="Listing not found")
        if chosen.status not in (ListingStatus.active, ListingStatus.sold_out):
            raise HTTPException(status_code=409, detail="Only active listings can be featured")
    for listing in db.query(Listing).all():
        listing.featured = bool(chosen and listing.id == chosen.id)
    db.commit()
    if chosen:
        db.refresh(chosen)
        view = _listing_view(chosen)
        if view.get("private"):
            view = admin_listing_view(view)
        return {"featured": view}
    return {"featured": None}


class DisableIn(BaseModel):
    user_id: str
    disabled: bool = True


@router.post("/users/disable")
def disable_user(
    payload: DisableIn,
    organizer: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == UserRole.organizer:
        raise HTTPException(status_code=409, detail="Cannot disable the organizer")
    user.disabled = bool(payload.disabled)
    db.commit()
    return {"user_id": user.id, "disabled": user.disabled}
