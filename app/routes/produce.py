import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Node, Produce, Listing, ListingStatus
from app.models.user import User
from app.dependencies import get_current_user

router = APIRouter(tags=["produce"])


class ProduceCreate(BaseModel):
    name: str
    category: str
    quantity_kg: float = 0.0
    kcal_per_kg: float = 0.0
    co2_kg_per_kg: float = 0.0


class ListingCreate(BaseModel):
    quantity_kg: float
    price_per_kg: float = 0.0
    pickup_point: str = ""
    is_free: bool = False


def _assert_node_owner(node_id: str, user: User, db: Session) -> Node:
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your node")
    return node


# --- Produce ---

@router.post("/nodes/{node_id}/produce", status_code=201)
def add_produce(node_id: str, payload: ProduceCreate,
                current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    node = _assert_node_owner(node_id, current_user, db)
    produce = Produce(id=str(uuid.uuid4()), node_id=node.id, **payload.model_dump())
    db.add(produce)
    db.commit()
    db.refresh(produce)
    return _produce_view(produce)


@router.get("/nodes/{node_id}/produce")
def list_produce(node_id: str, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return [_produce_view(p) for p in node.produce]


@router.patch("/nodes/{node_id}/produce/{produce_id}")
def update_produce(node_id: str, produce_id: str, payload: ProduceCreate,
                   current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _assert_node_owner(node_id, current_user, db)
    produce = db.query(Produce).filter(Produce.id == produce_id, Produce.node_id == node_id).first()
    if not produce:
        raise HTTPException(status_code=404, detail="Produce not found")
    for k, v in payload.model_dump().items():
        setattr(produce, k, v)
    db.commit()
    db.refresh(produce)
    return _produce_view(produce)


# --- Listings ---

@router.post("/nodes/{node_id}/produce/{produce_id}/listings", status_code=201)
def create_listing(node_id: str, produce_id: str, payload: ListingCreate,
                   current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    node = _assert_node_owner(node_id, current_user, db)
    produce = db.query(Produce).filter(Produce.id == produce_id, Produce.node_id == node_id).first()
    if not produce:
        raise HTTPException(status_code=404, detail="Produce not found")
    pickup = payload.pickup_point or node.description or f"{node.lat},{node.lng}"
    listing = Listing(
        id=str(uuid.uuid4()),
        node_id=node_id,
        produce_id=produce_id,
        quantity_kg=payload.quantity_kg,
        price_per_kg=payload.price_per_kg,
        pickup_point=pickup,
        is_free=payload.is_free,
        status=ListingStatus.active,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _listing_view(listing)


@router.get("/listings")
def browse_listings(lat: float | None = None, lng: float | None = None,
                    radius_km: float = 20.0, db: Session = Depends(get_db)):
    """Public browse — all active listings, optionally filtered by distance."""
    listings = db.query(Listing).filter(Listing.status == ListingStatus.active).all()
    result = []
    for l in listings:
        view = _listing_view(l)
        if lat is not None and lng is not None:
            km = _haversine(lat, lng, l.node.lat, l.node.lng)
            if km > radius_km:
                continue
            view["distance_km"] = round(km, 2)
        result.append(view)
    return result


@router.patch("/listings/{listing_id}/status")
def update_listing_status(listing_id: str, status: ListingStatus,
                          current_user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.node.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your listing")
    listing.status = status
    db.commit()
    return _listing_view(listing)


# --- Views ---

def _produce_view(p: Produce) -> dict:
    return {
        "id": p.id,
        "node_id": p.node_id,
        "name": p.name,
        "category": p.category,
        "quantity_kg": p.quantity_kg,
        "kcal_per_kg": p.kcal_per_kg,
        "co2_kg_per_kg": p.co2_kg_per_kg,
    }


def _listing_view(l: Listing) -> dict:
    return {
        "id": l.id,
        "node_id": l.node_id,
        "produce_id": l.produce_id,
        "produce_name": l.produce.name if l.produce else None,
        "quantity_kg": l.quantity_kg,
        "price_per_kg": l.price_per_kg,
        "is_free": l.is_free,
        "pickup_point": l.pickup_point,
        "status": l.status,
        "node_lat": l.node.lat if l.node else None,
        "node_lng": l.node.lng if l.node else None,
    }


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))
