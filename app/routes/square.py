"""Market square: who has what, when, and where."""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.db import get_db
from app.models import Node, Produce, Listing, ListingStatus, Transaction
from app.models.flare import DemandFlare, FlareStatus
from app.models.user import User, UserRole
from app.dependencies import get_current_user
from app.routes.produce import _haversine, _listing_view

router = APIRouter(tags=["square"])


class LotIn(BaseModel):
    produce_name: str
    category: str = "produce"
    quantity_kg: float
    price_per_kg: float = 0.0
    is_free: bool = False
    kcal_per_kg: float = 0.0
    co2_kg_per_kg: float = 0.4


class StallOpen(BaseModel):
    node_id: str
    available_from: datetime
    available_until: datetime
    pickup_point: str
    lots: list[LotIn]


class FlareCreate(BaseModel):
    item: str
    quantity_note: str = ""
    radius_km: float = 20.0
    lat: float | None = None
    lng: float | None = None


class ClaimRequest(BaseModel):
    quantity_kg: float | None = None


class GateSale(BaseModel):
    quantity_kg: float


def _matches(item: str, produce_name: str) -> bool:
    a = item.strip().lower()
    b = produce_name.strip().lower()
    if not a or not b:
        return False
    return a in b or b in a


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


@router.get("/square")
def market_square(
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float = 20.0,
    db: Session = Depends(get_db),
):
    """Public market square — stalls grouped by farm, with demand flares."""
    listings = (
        db.query(Listing)
        .options(
            joinedload(Listing.node).joinedload(Node.owner),
            joinedload(Listing.produce),
        )
        .filter(Listing.status == ListingStatus.active)
        .all()
    )
    flares = (
        db.query(DemandFlare)
        .options(joinedload(DemandFlare.buyer))
        .filter(DemandFlare.status == FlareStatus.open)
        .all()
    )

    stalls: dict[str, dict] = {}
    for listing in listings:
        node = listing.node
        if lat is not None and lng is not None:
            km = _haversine(lat, lng, node.lat, node.lng)
            if km > radius_km:
                continue
        else:
            km = None

        stall = stalls.get(node.id)
        if stall is None:
            stall = {
                "node_id": node.id,
                "farm_name": node.name,
                "farmer_name": node.owner.name if node.owner else "",
                "node_type": node.type.value if node.type else None,
                "lat": node.lat,
                "lng": node.lng,
                "pickup_point": listing.pickup_point,
                "available_from": _iso(listing.available_from),
                "available_until": _iso(listing.available_until),
                "distance_km": round(km, 2) if km is not None else None,
                "myc_balance": round(node.myc_tokens, 4),
                "matched_flares": [],
                "goods": [],
            }
            stalls[node.id] = stall
        else:
            if listing.available_from and (
                stall["available_from"] is None
                or listing.available_from.isoformat() < stall["available_from"]
            ):
                stall["available_from"] = _iso(listing.available_from)
            if listing.available_until and (
                stall["available_until"] is None
                or listing.available_until.isoformat() > stall["available_until"]
            ):
                stall["available_until"] = _iso(listing.available_until)

        good = _listing_view(listing)
        if km is not None:
            good["distance_km"] = round(km, 2)
        stall["goods"].append(good)

        for flare in flares:
            if _matches(flare.item, listing.produce.name if listing.produce else ""):
                flare_id = flare.id
                if flare_id not in stall["matched_flares"]:
                    stall["matched_flares"].append(flare_id)

    stall_list = list(stalls.values())
    stall_list.sort(key=lambda s: (s["distance_km"] is None, s["distance_km"] or 0))

    flare_views = []
    for flare in flares:
        matching_nodes = [
            s["node_id"] for s in stall_list if flare.id in s["matched_flares"]
        ]
        flare_views.append({
            "id": flare.id,
            "buyer_name": flare.buyer.name if flare.buyer else "",
            "item": flare.item,
            "quantity_note": flare.quantity_note,
            "radius_km": flare.radius_km,
            "status": flare.status.value if flare.status else "open",
            "matching_stalls": matching_nodes,
            "created_at": _iso(flare.created_at),
        })

    return {
        "stalls": stall_list,
        "flares": flare_views,
        "stall_count": len(stall_list),
        "lot_count": sum(len(s["goods"]) for s in stall_list),
    }


@router.post("/stalls", status_code=201)
def open_stall(
    payload: StallOpen,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Farmer posts a stall: when, where, and what's on the table."""
    if current_user.role not in (UserRole.farmer, UserRole.organizer):
        raise HTTPException(status_code=403, detail="Farmers only")
    node = db.query(Node).filter(Node.id == payload.node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your node")
    if not payload.lots:
        raise HTTPException(status_code=400, detail="A stall needs at least one lot")
    if payload.available_until <= payload.available_from:
        raise HTTPException(status_code=400, detail="until must be after from")

    created = []
    for lot in payload.lots:
        produce = (
            db.query(Produce)
            .filter(Produce.node_id == node.id, Produce.name == lot.produce_name)
            .first()
        )
        if produce is None:
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
        else:
            produce.quantity_kg = (produce.quantity_kg or 0) + lot.quantity_kg

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
        "node_id": node.id,
        "farm_name": node.name,
        "pickup_point": payload.pickup_point,
        "available_from": _iso(payload.available_from),
        "available_until": _iso(payload.available_until),
        "lots": [_listing_view(l) for l in created],
    }


@router.get("/catalog")
def catalog(
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float = 40.0,
    db: Session = Depends(get_db),
):
    """Flat grocery list across the farmer network. Skip the shop."""
    square = market_square(lat=lat, lng=lng, radius_km=radius_km, db=db)
    items = []
    for stall in square["stalls"]:
        for good in stall["goods"]:
            items.append({
                **good,
                "farm_name": stall["farm_name"],
                "farmer_name": stall["farmer_name"],
                "pickup_point": stall["pickup_point"],
                "available_from": stall["available_from"],
                "available_until": stall["available_until"],
                "distance_km": stall["distance_km"],
                "golden": bool(stall["matched_flares"]),
            })
    items.sort(key=lambda g: (g["distance_km"] is None, g["distance_km"] or 0, g["produce_name"] or ""))
    return {"items": items, "count": len(items), "flares": square["flares"]}


@router.post("/listings/{listing_id}/gate")
def gate_sale(
    listing_id: str,
    payload: GateSale,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cash at the gate. Stock goes down. No buyer, no euros, no sales row."""
    listing = (
        db.query(Listing)
        .options(joinedload(Listing.node), joinedload(Listing.produce))
        .filter(Listing.id == listing_id)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.node.owner_id != current_user.id and current_user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Not your stall")
    if listing.status not in (ListingStatus.active, ListingStatus.reserved):
        raise HTTPException(status_code=409, detail="Nothing left on the table")
    if payload.quantity_kg <= 0 or payload.quantity_kg > listing.quantity_kg:
        raise HTTPException(status_code=400, detail="Quantity exceeds what's on the table")
    listing.quantity_kg -= payload.quantity_kg
    if listing.quantity_kg <= 0:
        listing.quantity_kg = 0
        listing.status = ListingStatus.completed
    db.commit()
    db.refresh(listing)
    return {
        "listing_id": listing.id,
        "remaining_kg": listing.quantity_kg,
        "status": listing.status,
        "settled": "cash_at_gate",
    }


@router.post("/listings/{listing_id}/claim")
def claim_listing(
    listing_id: str,
    payload: ClaimRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Buyer reserves a lot. Pickup still happens at the stall's when/where."""
    listing = (
        db.query(Listing)
        .options(joinedload(Listing.produce), joinedload(Listing.node))
        .filter(Listing.id == listing_id)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != ListingStatus.active:
        raise HTTPException(status_code=409, detail="Listing is not active")
    qty = payload.quantity_kg if payload.quantity_kg is not None else listing.quantity_kg
    if qty <= 0 or qty > listing.quantity_kg:
        raise HTTPException(status_code=400, detail="Quantity exceeds listing amount")
    listing.status = ListingStatus.reserved
    db.commit()
    db.refresh(listing)
    return {
        **_listing_view(listing),
        "claimed_by": current_user.name,
        "claimed_qty_kg": qty,
        "note": "Reserved. Meet the farmer at the posted when and where to complete the trade.",
    }


@router.post("/flares", status_code=201)
def raise_flare(
    payload: FlareCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Buyer broadcasts a need — lights up matching stalls (golden spores)."""
    flare = DemandFlare(
        id=str(uuid.uuid4()),
        buyer_id=current_user.id,
        item=payload.item,
        quantity_note=payload.quantity_note,
        radius_km=payload.radius_km,
        lat=payload.lat,
        lng=payload.lng,
        status=FlareStatus.open,
    )
    db.add(flare)
    db.commit()
    db.refresh(flare)
    return {
        "id": flare.id,
        "item": flare.item,
        "quantity_note": flare.quantity_note,
        "radius_km": flare.radius_km,
        "status": flare.status.value,
    }


@router.get("/flares")
def list_flares(db: Session = Depends(get_db)):
    flares = (
        db.query(DemandFlare)
        .options(joinedload(DemandFlare.buyer))
        .filter(DemandFlare.status == FlareStatus.open)
        .all()
    )
    return [
        {
            "id": f.id,
            "buyer_name": f.buyer.name if f.buyer else "",
            "item": f.item,
            "quantity_note": f.quantity_note,
            "radius_km": f.radius_km,
            "status": f.status.value if f.status else "open",
            "created_at": _iso(f.created_at),
        }
        for f in flares
    ]


@router.post("/flares/{flare_id}/close")
def close_flare(
    flare_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    flare = db.query(DemandFlare).filter(DemandFlare.id == flare_id).first()
    if not flare:
        raise HTTPException(status_code=404, detail="Flare not found")
    if flare.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your flare")
    flare.status = FlareStatus.closed
    db.commit()
    return {"id": flare.id, "status": flare.status.value}


@router.get("/ledger")
def public_ledger(limit: int = 20, db: Session = Depends(get_db)):
    """Recent mycelium trades — append-only, newest first."""
    txs = (
        db.query(Transaction)
        .options(joinedload(Transaction.listing).joinedload(Listing.produce),
                 joinedload(Transaction.listing).joinedload(Listing.node),
                 joinedload(Transaction.buyer))
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": tx.id,
            "from_farm": tx.listing.node.name if tx.listing and tx.listing.node else "",
            "produce": tx.listing.produce.name if tx.listing and tx.listing.produce else "",
            "buyer": tx.buyer.name if tx.buyer else "",
            "quantity_kg": tx.quantity_kg,
            "distance_km": tx.distance_km,
            "myc_tokens_minted": round(tx.myc_tokens_minted, 4),
            "co2_saved_kg": round(tx.co2_saved_kg, 4),
            "created_at": _iso(tx.created_at),
        }
        for tx in txs
    ]
