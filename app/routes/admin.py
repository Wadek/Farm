"""Organizer dashboard: farms, featured listing, counts."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.db import get_db
from app.models import Node, Listing, ListingStatus, User
from app.models.ask import PickupAsk
from app.dependencies import require_organizer
from app.routes.produce import _listing_view
from app.routes.square import _iso

router = APIRouter(prefix="/admin", tags=["admin"])


class FeatureIn(BaseModel):
    listing_id: str | None = None


def _farm_row(node: Node, listings: list[Listing]) -> dict:
    claimed = node.claimed_at is not None
    owner = node.owner
    return {
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
        "listing_count": len(listings),
        "demo_count": sum(1 for l in listings if getattr(l, "demo", False)),
        "listings": [_listing_view(l) for l in listings],
    }


@router.get("/overview")
def admin_overview(
    organizer: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    nodes = db.query(Node).options(joinedload(Node.owner)).order_by(Node.created_at.desc()).all()
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
    return {
        "farm_count": len(farms),
        "unclaimed_count": sum(1 for f in farms if f["is_unclaimed"]),
        "listing_count": len(listings),
        "demo_count": sum(1 for l in listings if getattr(l, "demo", False)),
        "ask_count": asks,
        "featured": featured,
        "farms": farms,
        "listings": [_listing_view(l) for l in listings],
    }


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
        return {"featured": _listing_view(chosen)}
    return {"featured": None}
