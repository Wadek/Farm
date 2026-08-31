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


def _b64url(raw: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _generate_keys() -> tuple[str, str]:
    """Raw 32-byte EC private scalar + uncompressed public point, both url-safe b64.

    Stored without PEM headers so the working tree does not contain
    ``BEGIN PRIVATE KEY`` material.
    """
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    priv = ec.generate_private_key(ec.SECP256R1())
    private_raw = priv.private_numbers().private_value.to_bytes(32, "big")
    public_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return _b64url(private_raw), _b64url(public_raw)


def vapid_keys() -> tuple[str, str]:
    """Return (private_b64, public_key_urlsafe). Persist so subscriptions stay valid."""
    global _keys
    if _keys:
        return _keys
    if settings.vapid_private_key and settings.vapid_public_key:
        _keys = (settings.vapid_private_key, settings.vapid_public_key)
        return _keys
    path = _vapid_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        private_key = data.get("private_key") or data.get("private_pem")
        public_key = data.get("public_key")
        if private_key and public_key and "BEGIN" not in private_key:
            _keys = (private_key, public_key)
            return _keys
    private_key, public_key = _generate_keys()
    path.write_text(
        json.dumps({"private_key": private_key, "public_key": public_key}),
        encoding="utf-8",
    )
    _keys = (private_key, public_key)
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
    private_key, _public = vapid_keys()
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
                vapid_private_key=private_key,
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
