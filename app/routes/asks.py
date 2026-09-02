"""Ask to pick up — the neighbor phone call, in the app and by SMS."""

import re
import secrets
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.db import get_db
from app.config import settings
from app.models import Listing, ListingStatus, Node, User, UserRole
from app.models.ask import PickupAsk, AskStatus, SmsLog
from app.models.message import Message
from app.dependencies import get_current_user
from app.services import sms as sms_svc

router = APIRouter(tags=["asks"])
DECLINE = {"ei", "ei.", "no", "no.", "en voi", "ei pysty", "ei onnistu"}


class AskCreate(BaseModel):
    listing_id: str
    quantity: float = 1.0
    note: str = ""


class AskReply(BaseModel):
    when_text: str = ""
    decline: bool = False


class AskAvailable(BaseModel):
    quantity: float | None = None
    when_text: str = ""


def _iso(dt):
    return dt.isoformat() if dt else None


def _ask_view(ask: PickupAsk) -> dict:
    listing = ask.listing
    produce = listing.produce.name if listing and listing.produce else ""
    pickup = listing.pickup_point if listing else ""
    farm = listing.node.name if listing and listing.node else ""
    listing_status = listing.status.value if listing and listing.status else "active"
    return {
        "id": ask.id,
        "token": ask.token,
        "listing_id": ask.listing_id,
        "produce": produce,
        "farm_name": farm,
        "pickup_point": pickup,
        "sold_out": listing_status == "sold_out",
        "buyer_name": ask.buyer.name if ask.buyer else "",
        "farmer_name": ask.farmer.name if ask.farmer else "",
        "buyer_id": ask.buyer_id,
        "farmer_id": ask.farmer_id,
        "quantity": ask.quantity,
        "unit": ask.unit,
        "note": ask.note,
        "status": ask.status.value if ask.status else "asked",
        "offer_text": ask.offer_text,
        "picked_up_by": ask.picked_up_by,
        "picked_up_at": _iso(ask.picked_up_at),
        "buyer_verified_at": _iso(ask.buyer_verified_at),
        "farmer_verified_at": _iso(ask.farmer_verified_at),
        "acknowledged_at": _iso(ask.acknowledged_at),
        "created_at": _iso(ask.created_at),
        "updated_at": _iso(ask.updated_at),
        "reply_url": f"{settings.public_base_url.rstrip('/')}/r/{ask.token}",
    }


def _alert(db: Session, sender_id: str, recipient_id: str, listing_id: str | None, body: str) -> None:
    db.add(Message(
        id=str(uuid.uuid4()),
        sender_id=sender_id,
        recipient_id=recipient_id,
        listing_id=listing_id,
        body=body,
    ))


def _farmer_sms(ask: PickupAsk) -> str:
    v = _ask_view(ask)
    qty = f"{ask.quantity:g} {ask.unit}"
    extra = f" ({ask.note})" if ask.note else ""
    if v.get("sold_out"):
        return (
            f"{v['buyer_name']} pyytää {qty} {v['produce']} (loppu). "
            f"Vastaa milloin on taas, esim. la 10 — tai avaa {v['reply_url']}"
        )
    return (
        f"{v['buyer_name']} kysyy: voinko hakea {qty} {v['produce']}?{extra} "
        f"Vastaa ajalla, esim. la 10 — tai avaa {v['reply_url']}"
    )


def _buyer_sms(ask: PickupAsk) -> str:
    v = _ask_view(ask)
    if ask.status == AskStatus.declined:
        return f"{v['farmer_name']}: ei onnistu nyt ({v['produce']})."
    when = ask.offer_text or "sopii"
    place = f" {v['pickup_point']}" if v["pickup_point"] else ""
    return f"{v['farmer_name']}: {when}.{place}"


def _apply_reply(ask: PickupAsk, when_text: str, decline: bool, db: Session) -> PickupAsk:
    text = (when_text or "").strip()
    if decline or text.lower() in DECLINE:
        ask.status = AskStatus.declined
        ask.offer_text = text or "ei"
        db.add(Message(
            id=str(uuid.uuid4()), sender_id=ask.farmer_id, recipient_id=ask.buyer_id,
            listing_id=ask.listing_id, body=f"The farmer cannot fulfill {ask.quantity:g} {ask.unit} {ask.listing.produce.name if ask.listing and ask.listing.produce else ''}."
        ))
    else:
        if not text:
            raise HTTPException(status_code=400, detail="Send a time, e.g. la 10")
        listing = ask.listing
        if listing and listing.quantity_kg < ask.quantity:
            listing.quantity_kg += ask.quantity - max(listing.quantity_kg, 0)
        if listing:
            listing.status = ListingStatus.active
        ask.status = AskStatus.confirmed
        ask.offer_text = text
        farmer_name = ask.farmer.name if ask.farmer else "Farmer"
        _alert(
            db, ask.farmer_id, ask.buyer_id, ask.listing_id,
            f"{farmer_name} replied: {text}",
        )
    ask.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ask)
    if ask.buyer and ask.buyer.phone:
        sms_svc.send_sms(db, ask.buyer.phone, _buyer_sms(ask), ask.id)
    return ask


@router.post("/asks", status_code=201)
def create_ask(
    payload: AskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = (
        db.query(Listing)
        .options(joinedload(Listing.node).joinedload(Node.owner), joinedload(Listing.produce))
        .filter(Listing.id == payload.listing_id)
        .first()
    )
    if not listing or not listing.node or not listing.node.owner:
        raise HTTPException(status_code=404, detail="Listing not found")
    farmer = listing.node.owner
    if farmer.role not in (UserRole.farmer, UserRole.organizer):
        raise HTTPException(status_code=409, detail="Listing owner cannot receive pickup requests")
    if current_user.role not in (UserRole.buyer, UserRole.farmer, UserRole.organizer):
        raise HTTPException(status_code=403, detail="Only customers, farmers, and admins can send pickup requests")
    if farmer.id == current_user.id:
        raise HTTPException(status_code=400, detail="That's your own listing")
    ask = PickupAsk(
        id=str(uuid.uuid4()),
        token=secrets.token_urlsafe(8),
        listing_id=listing.id,
        buyer_id=current_user.id,
        farmer_id=farmer.id,
        quantity=payload.quantity,
        unit=listing.unit or "kg",
        note=payload.note.strip(),
        status=AskStatus.asked,
    )
    db.add(ask)
    produce = listing.produce.name if listing.produce else "produce"
    _alert(
        db, current_user.id, farmer.id, listing.id,
        f"{current_user.name} asked for {payload.quantity:g} {listing.unit or 'kg'} {produce}.",
    )
    db.commit()
    db.refresh(ask)
    ask = (
        db.query(PickupAsk)
        .options(
            joinedload(PickupAsk.listing).joinedload(Listing.produce),
            joinedload(PickupAsk.listing).joinedload(Listing.node),
            joinedload(PickupAsk.buyer),
            joinedload(PickupAsk.farmer),
        )
        .filter(PickupAsk.id == ask.id)
        .first()
    )
    sms_result = {"sent": False, "provider": "none"}
    if farmer.phone:
        sms_result = sms_svc.send_sms(db, farmer.phone, _farmer_sms(ask), ask.id)
    view = _ask_view(ask)
    view["sms"] = sms_result
    return view


@router.get("/asks")
def list_asks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = (
        db.query(PickupAsk)
        .options(
            joinedload(PickupAsk.listing).joinedload(Listing.produce),
            joinedload(PickupAsk.listing).joinedload(Listing.node),
            joinedload(PickupAsk.buyer),
            joinedload(PickupAsk.farmer),
        )
        .order_by(PickupAsk.created_at.desc())
    )
    if current_user.role == UserRole.organizer:
        rows = q.all()
    elif current_user.role == UserRole.farmer:
        rows = q.filter(
            ((PickupAsk.farmer_id == current_user.id) | (PickupAsk.buyer_id == current_user.id))
            & PickupAsk.status.in_((AskStatus.asked, AskStatus.offered, AskStatus.confirmed))
        ).all()
    else:
        rows = q.filter(PickupAsk.buyer_id == current_user.id).all()
    return [_ask_view(a) for a in rows]


@router.post("/asks/{ask_id}/reply")
def reply_ask(
    ask_id: str,
    payload: AskReply,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ask = (
        db.query(PickupAsk)
        .options(
            joinedload(PickupAsk.listing).joinedload(Listing.produce),
            joinedload(PickupAsk.listing).joinedload(Listing.node),
            joinedload(PickupAsk.buyer),
            joinedload(PickupAsk.farmer),
        )
        .filter(PickupAsk.id == ask_id)
        .first()
    )
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    if ask.farmer_id != current_user.id and current_user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Not your ask")
    ask = _apply_reply(ask, payload.when_text, payload.decline, db)
    return _ask_view(ask)


@router.post("/asks/{ask_id}/available")
def mark_available(
    ask_id: str,
    payload: AskAvailable,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ask = (
        db.query(PickupAsk)
        .options(
            joinedload(PickupAsk.listing).joinedload(Listing.node).joinedload(Node.owner),
            joinedload(PickupAsk.listing).joinedload(Listing.produce),
            joinedload(PickupAsk.buyer),
            joinedload(PickupAsk.farmer),
        )
        .filter(PickupAsk.id == ask_id)
        .first()
    )
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    if ask.farmer_id != current_user.id and current_user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Not your ask")
    if ask.status != AskStatus.asked:
        raise HTTPException(status_code=409, detail="Request is already answered")
    quantity = payload.quantity if payload.quantity is not None else ask.quantity
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    listing = ask.listing
    if listing.quantity_kg < quantity:
        listing.quantity_kg += quantity - max(listing.quantity_kg, 0)
    listing.status = ListingStatus.active
    ask.status = AskStatus.confirmed
    ask.offer_text = payload.when_text.strip() or "Ready for pickup"
    ask.updated_at = datetime.now(timezone.utc)
    farmer_name = ask.farmer.name if ask.farmer else current_user.name
    _alert(
        db, ask.farmer_id, ask.buyer_id, ask.listing_id,
        f"{farmer_name} replied: {ask.offer_text}",
    )
    db.commit()
    db.refresh(ask)
    if ask.buyer and ask.buyer.phone:
        sms_svc.send_sms(db, ask.buyer.phone, _buyer_sms(ask), ask.id)
    return _ask_view(_load_token(ask.token, db))


@router.get("/alerts")
def list_alerts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Message).filter(Message.recipient_id == current_user.id).order_by(Message.created_at.desc()).limit(30).all()
    return [{"id": row.id, "body": row.body, "read": row.read, "created_at": _iso(row.created_at)} for row in rows]


@router.post("/alerts/{alert_id}/read")
def read_alert(alert_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(Message).filter(Message.id == alert_id, Message.recipient_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    row.read = True
    db.commit()
    return {"id": row.id, "read": True}


@router.post("/asks/{ask_id}/remind")
def remind_trade(ask_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Admin only")
    ask = db.query(PickupAsk).filter(PickupAsk.id == ask_id).first()
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    produce = ask.listing.produce.name if ask.listing and ask.listing.produce else "the order"
    db.add_all([
        Message(id=str(uuid.uuid4()), sender_id=current_user.id, recipient_id=ask.buyer_id,
                listing_id=ask.listing_id, body=f"Reminder: do you still need {ask.quantity:g} {ask.unit} {produce}?"),
        Message(id=str(uuid.uuid4()), sender_id=current_user.id, recipient_id=ask.farmer_id,
                listing_id=ask.listing_id, body=f"Reminder: do you have {ask.quantity:g} {ask.unit} {produce} ready?"),
    ])
    db.commit()
    return {"status": "sent", "ask_id": ask.id}


@router.post("/asks/{ask_id}/picked-up")
def confirm_picked_up(
    ask_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Customer closes a confirmed pickup after collecting the order."""
    ask = db.query(PickupAsk).filter(PickupAsk.id == ask_id).first()
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    if ask.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the customer can confirm pickup")
    if ask.status not in (AskStatus.confirmed, AskStatus.offered):
        raise HTTPException(status_code=409, detail="Pickup is not confirmed")
    ask.buyer_verified_at = datetime.now(timezone.utc)
    ask.picked_up_by = current_user.name
    ask.picked_up_at = ask.buyer_verified_at
    if ask.farmer_verified_at:
        ask.status = AskStatus.picked_up
    else:
        ask.status = AskStatus.confirmed
        db.add(Message(
            id=str(uuid.uuid4()), sender_id=ask.buyer_id, recipient_id=ask.farmer_id,
            listing_id=ask.listing_id, body="Customer verified pickup. Please verify the handoff to complete the transaction."
        ))
    ask.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ask)
    return _ask_view(_load_token(ask.token, db))


def _undo_pickup(ask: PickupAsk, current_user: User, db: Session) -> PickupAsk:
    if current_user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Admin only")
    if ask.status != AskStatus.picked_up:
        raise HTTPException(status_code=409, detail="Pickup is not marked complete")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    picked = ask.picked_up_at.replace(tzinfo=None) if ask.picked_up_at and getattr(ask.picked_up_at, "tzinfo", None) else ask.picked_up_at
    if picked is None or (now - picked).total_seconds() > 300:
        raise HTTPException(status_code=409, detail="Pickup can only be undone for five minutes")
    ask.status = AskStatus.confirmed
    ask.picked_up_by = None
    ask.picked_up_at = None
    ask.buyer_verified_at = None
    ask.farmer_verified_at = None
    ask.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ask)
    return ask


@router.post("/asks/{ask_id}/undo-pickup")
def undo_pickup(ask_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ask = db.query(PickupAsk).filter(PickupAsk.id == ask_id).first()
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    return _ask_view(_load_token(_undo_pickup(ask, current_user, db).token, db))


@router.post("/asks/{ask_id}/acknowledge")
def acknowledge_ask(ask_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Farmer saw the incoming request. Does not fulfill, decline, or change handoff state."""
    ask = db.query(PickupAsk).filter(PickupAsk.id == ask_id).first()
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    if ask.farmer_id != current_user.id and current_user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Not your ask")
    if not ask.acknowledged_at:
        ask.acknowledged_at = datetime.now(timezone.utc)
        ask.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(ask)
    return _ask_view(_load_token(ask.token, db))


@router.post("/asks/{ask_id}/withdraw")
def withdraw_ask(ask_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ask = db.query(PickupAsk).filter(PickupAsk.id == ask_id).first()
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    if current_user.role != UserRole.organizer and current_user.id not in (ask.buyer_id, ask.farmer_id):
        raise HTTPException(status_code=403, detail="Not your order")
    if ask.status in (AskStatus.picked_up, AskStatus.withdrawn):
        raise HTTPException(status_code=409, detail="Order is already closed")
    ask.status = AskStatus.withdrawn
    ask.offer_text = "Withdrawn by " + current_user.name
    ask.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _ask_view(_load_token(ask.token, db))


@router.post("/asks/{ask_id}/farmer-picked-up")
def farmer_confirm_picked_up(
    ask_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ask = db.query(PickupAsk).filter(PickupAsk.id == ask_id).first()
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    if ask.farmer_id != current_user.id and current_user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Not your ask")
    if ask.status not in (AskStatus.confirmed, AskStatus.offered):
        raise HTTPException(status_code=409, detail="Pickup is not confirmed")
    ask.farmer_verified_at = datetime.now(timezone.utc)
    ask.picked_up_by = current_user.name
    ask.picked_up_at = ask.farmer_verified_at
    if ask.buyer_verified_at:
        ask.status = AskStatus.picked_up
    else:
        ask.status = AskStatus.confirmed
        db.add(Message(
            id=str(uuid.uuid4()), sender_id=ask.farmer_id, recipient_id=ask.buyer_id,
            listing_id=ask.listing_id, body="Farmer verified pickup. Please verify the handoff to complete the transaction."
        ))
    ask.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _ask_view(_load_token(ask.token, db))


@router.get("/asks/public/{token}")
def public_ask(token: str, db: Session = Depends(get_db)):
    ask = _load_token(token, db)
    return _ask_view(ask)


@router.post("/asks/public/{token}/reply")
def public_reply(token: str, payload: AskReply, db: Session = Depends(get_db)):
    ask = _load_token(token, db)
    ask = _apply_reply(ask, payload.when_text, payload.decline, db)
    return _ask_view(ask)


def _load_token(token: str, db: Session) -> PickupAsk:
    ask = (
        db.query(PickupAsk)
        .options(
            joinedload(PickupAsk.listing).joinedload(Listing.produce),
            joinedload(PickupAsk.listing).joinedload(Listing.node),
            joinedload(PickupAsk.buyer),
            joinedload(PickupAsk.farmer),
        )
        .filter(PickupAsk.token == token)
        .first()
    )
    if not ask:
        raise HTTPException(status_code=404, detail="Ask not found")
    return ask


@router.post("/sms/inbound")
async def sms_inbound(request: Request, db: Session = Depends(get_db)):
    """46elks (from, to, message) or Twilio (From, To, Body). Farmer texts a time."""
    form = {}
    try:
        form = dict(await request.form())
    except Exception:
        form = {}
    if not form:
        try:
            form = await request.json()
        except Exception:
            form = {}
    from_phone = str(form.get("from") or form.get("From") or "")
    body = str(form.get("message") or form.get("Body") or form.get("text") or "").strip()
    if not from_phone or not body:
        raise HTTPException(status_code=400, detail="Need from + message")

    farmers = db.query(User).filter(User.role.in_([UserRole.farmer, UserRole.organizer])).all()
    farmer = next((u for u in farmers if u.phone and sms_svc.same_phone(u.phone, from_phone)), None)
    log = SmsLog(
        id=str(uuid.uuid4()),
        direction="in",
        phone=sms_svc.e164(from_phone) or from_phone,
        body=body,
        provider="inbound",
    )
    db.add(log)
    if not farmer:
        db.commit()
        return PlainTextResponse("ok")

    ask = (
        db.query(PickupAsk)
        .options(
            joinedload(PickupAsk.listing).joinedload(Listing.produce),
            joinedload(PickupAsk.listing).joinedload(Listing.node),
            joinedload(PickupAsk.buyer),
            joinedload(PickupAsk.farmer),
        )
        .filter(PickupAsk.farmer_id == farmer.id, PickupAsk.status == AskStatus.asked)
        .order_by(PickupAsk.created_at.desc())
        .first()
    )
    if not ask:
        db.commit()
        return PlainTextResponse("ok")
    log.ask_id = ask.id
    db.commit()
    _apply_reply(ask, body, False, db)
    return PlainTextResponse("ok")


@router.get("/sms")
def list_sms(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != UserRole.organizer:
        raise HTTPException(status_code=403, detail="Admin only")
    rows = db.query(SmsLog).order_by(SmsLog.created_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "direction": r.direction,
            "phone": r.phone,
            "body": r.body,
            "ask_id": r.ask_id,
            "provider": r.provider,
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]
