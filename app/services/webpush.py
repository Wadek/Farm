"""Web Push (VAPID) so the iPhone PWA can alert when Satokori is closed."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings

log = logging.getLogger("satokori.push")

_keys: tuple[str, str] | None = None


def _vapid_path() -> Path:
    data_dir = Path("/data") if Path("/data").is_dir() else Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "vapid.json"


def _generate_keys() -> tuple[str, str]:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    import base64

    priv = ec.generate_private_key(ec.SECP256R1())
    private_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_key = base64.urlsafe_b64encode(public_raw).rstrip(b"=").decode()
    return private_pem, public_key


def vapid_keys() -> tuple[str, str]:
    """Return (private_pem, public_key_urlsafe). Persist so subscriptions stay valid."""
    global _keys
    if _keys:
        return _keys
    if settings.vapid_private_key and settings.vapid_public_key:
        _keys = (settings.vapid_private_key, settings.vapid_public_key)
        return _keys
    path = _vapid_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        _keys = (data["private_pem"], data["public_key"])
        return _keys
    private_pem, public_key = _generate_keys()
    path.write_text(
        json.dumps({"private_pem": private_pem, "public_key": public_key}),
        encoding="utf-8",
    )
    _keys = (private_pem, public_key)
    return _keys


def public_key() -> str:
    return vapid_keys()[1]


def send_to_user(
    db,
    user_id: str,
    title: str = "Satokori",
    body: str = "",
    tag: str = "satokori",
    url: str = "/",
) -> int:
    """Encrypt and POST to each of the user's device endpoints. Drop 404/410 subs."""
    from pywebpush import webpush, WebPushException
    from app.models.push_subscription import PushSubscription

    rows = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    if not rows:
        return 0
    private_pem, _public = vapid_keys()
    payload = json.dumps({"title": title or "Satokori", "body": body or "", "tag": tag, "url": url})
    sent = 0
    dead = []
    for row in rows:
        try:
            webpush(
                subscription_info={
                    "endpoint": row.endpoint,
                    "keys": {"p256dh": row.p256dh, "auth": row.auth_key},
                },
                data=payload,
                vapid_private_key=private_pem,
                vapid_claims={"sub": settings.vapid_contact},
                ttl=86400,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                dead.append(row)
            else:
                log.warning("web push failed for %s: %s", row.id, exc)
        except Exception as exc:
            log.warning("web push error for %s: %s", row.id, exc)
    for row in dead:
        db.delete(row)
    if dead:
        db.commit()
    return sent
