import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Listing, ListingStatus, Transaction, Node, User
from app.services import token_engine, geo

router = APIRouter(prefix="/transactions", tags=["transactions"])


class CompleteListingRequest(BaseModel):
    listing_id: str
    buyer_id: str
    quantity_kg: float
    is_walking: bool = False


@router.post("/complete")
def complete_listing(req: CompleteListingRequest, db: Session = Depends(get_db)):
    """
    Complete a listing transaction. Calculates distance, mints MYC tokens,
    writes an append-only ledger entry, and updates balances.
    """
    listing = db.query(Listing).filter(Listing.id == req.listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != ListingStatus.active:
        raise HTTPException(status_code=409, detail="Listing is not active")
    if req.quantity_kg > listing.quantity_kg:
        raise HTTPException(status_code=400, detail="Quantity exceeds listing amount")

    buyer = db.query(User).filter(User.id == req.buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")

    seller_node = db.query(Node).filter(Node.id == listing.node_id).first()

    # Distance: buyer has no fixed location, use listing pickup point coords via seller node
    # When buyer nodes are implemented this will use their node coords
    distance_km = 0.0
    buyer_nodes = db.query(Node).filter(Node.owner_id == req.buyer_id).first()
    if buyer_nodes:
        distance_km = geo.haversine(
            buyer_nodes.lat, buyer_nodes.lng,
            seller_node.lat, seller_node.lng,
        )

    produce = listing.produce
    result = token_engine.calculate(
        kcal_per_kg=produce.kcal_per_kg,
        store_co2_per_kg=produce.co2_kg_per_kg,
        local_co2_per_kg=produce.co2_kg_per_kg,
        mass_kg=req.quantity_kg,
        distance_km=distance_km,
        is_walking=req.is_walking,
    )

    # Append-only ledger entry
    tx = Transaction(
        id=str(uuid.uuid4()),
        listing_id=listing.id,
        buyer_id=req.buyer_id,
        quantity_kg=req.quantity_kg,
        distance_km=result.distance_km,
        is_walking=str(req.is_walking),
        co2_saved_kg=result.co2_saved_kg,
        kwh_equiv=result.kwh_equiv,
        myc_tokens_minted=result.myc_tokens,
    )
    db.add(tx)

    # Update node MYC balance and listing status
    seller_node.myc_tokens += result.myc_tokens
    listing.quantity_kg -= req.quantity_kg
    if listing.quantity_kg <= 0:
        listing.status = ListingStatus.completed

    db.commit()
    db.refresh(tx)

    return {
        "transaction_id": tx.id,
        "myc_tokens_minted": round(result.myc_tokens, 4),
        "co2_saved_kg": round(result.co2_saved_kg, 4),
        "kwh_equiv": round(result.kwh_equiv, 4),
        "energy_value_eur": round(result.energy_value_eur, 4),
        "distance_km": round(result.distance_km, 3),
        "seller_myc_balance": round(seller_node.myc_tokens, 4),
    }


@router.get("/node/{node_id}")
def node_ledger(node_id: str, db: Session = Depends(get_db)):
    """Return full append-only transaction ledger for a node."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    listings = db.query(Listing).filter(Listing.node_id == node_id).all()
    listing_ids = [l.id for l in listings]
    txs = db.query(Transaction).filter(Transaction.listing_id.in_(listing_ids)).all()

    return {
        "node_id": node_id,
        "myc_balance": round(node.myc_tokens, 4),
        "transaction_count": len(txs),
        "ledger": [
            {
                "id": tx.id,
                "listing_id": tx.listing_id,
                "quantity_kg": tx.quantity_kg,
                "distance_km": tx.distance_km,
                "co2_saved_kg": round(tx.co2_saved_kg, 4),
                "myc_tokens_minted": round(tx.myc_tokens_minted, 4),
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in txs
        ],
    }
