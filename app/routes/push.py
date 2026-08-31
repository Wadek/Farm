"""Web Push subscription endpoints. The public VAPID key is not a secret."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.models.push_subscription import PushSubscription
from app.dependencies import get_current_user
from app.services import webpush as push_svc

router = APIRouter(tags=["push"])


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribe(BaseModel):
    endpoint: str
    keys: PushKeys


class PushUnsubscribe(BaseModel):
    endpoint: str = Field(min_length=8)


def _https_endpoint(endpoint: str) -> str:
    url = (endpoint or "").strip()
    if not url.startswith("https://") or len(url) > 2048:
        raise HTTPException(status_code=400, detail="Push endpoint must be https")
    return url


@router.get("/push/vapid-public")
def vapid_public():
    return {"public_key": push_svc.public_key()}


@router.post("/push/subscribe")
def subscribe(
    payload: PushSubscribe,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    endpoint = _https_endpoint(payload.endpoint)
    p256dh = (payload.keys.p256dh or "").strip()
    auth_key = (payload.keys.auth or "").strip()
    if not p256dh or not auth_key:
        raise HTTPException(status_code=400, detail="Push keys required")
    row = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    now = datetime.now(timezone.utc)
    if row:
        row.user_id = current_user.id
        row.p256dh = p256dh
        row.auth_key = auth_key
        row.updated_at = now
    else:
        row = PushSubscription(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth_key=auth_key,
        )
        db.add(row)
    db.commit()
    return {"status": "subscribed", "id": row.id}


@router.delete("/push/subscribe")
def unsubscribe(
    payload: PushUnsubscribe,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    endpoint = _https_endpoint(payload.endpoint)
    row = db.query(PushSubscription).filter(
        PushSubscription.endpoint == endpoint,
        PushSubscription.user_id == current_user.id,
    ).first()
    if row:
        db.delete(row)
        db.commit()
    return {"status": "unsubscribed"}
