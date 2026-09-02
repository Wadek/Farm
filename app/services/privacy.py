"""AES-GCM lockbox helpers. Same construction as WakaGym (32-byte key, 12-byte IV).
The server never stores the recovery key and cannot open ciphertext."""

from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def unb64u(text: str) -> bytes:
    s = str(text or "").replace("-", "+").replace("_", "/")
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def generate_recovery_key() -> str:
    return b64u(os.urandom(32))


def encrypt_json(obj: dict, key_b64: str) -> dict:
    raw = unb64u(key_b64)
    if len(raw) != 32:
        raise ValueError("bad recovery key")
    iv = os.urandom(12)
    ct = AESGCM(raw).encrypt(iv, json.dumps(obj).encode("utf-8"), None)
    return {"iv" : b64u(iv), "ct": b64u(ct)}


def decrypt_json(iv: str, ct: str, key_b64: str):
    raw = unb64u(key_b64)
    if len(raw) != 32:
        raise ValueError("bad recovery key")
    pt = AESGCM(raw).decrypt(unb64u(iv), unb64u(ct), None)
    return json.loads(pt.decode("utf-8"))


def is_sealed(obj) -> bool:
    if obj is None:
        return False
    if hasattr(obj, "privacy_iv"):
        return bool(getattr(obj, "private", False) and obj.privacy_iv and obj.privacy_ct)
    return bool(obj.get("private") and obj.get("v") and obj.get("iv") and obj.get("ct"))


def admin_listing_view(view: dict) -> dict:
    """What an organizer may see of a sealed listing. No harvest details."""
    if not view.get("private"):
        return view
    drop = view.get("drop")
    return {
        "id": view.get("id"),
        "node_id": view.get("node_id"),
        "private": True,
        "category": view.get("category"),
        "status": view.get("status"),
        "drop": {"ring_name": (drop or {}).get("ring_name"), "place": (drop or {}).get("place")} if drop else None,
        "image_url": view.get("image_url"),
        "produce_name": None,
        "quantity_kg": None,
        "price_per_kg": None,
        "pickup_point": None,
        "node_name": view.get("node_name"),
        "farm_name": view.get("node_name"),
        "created_at": view.get("created_at"),
        "featured": view.get("featured"),
        "demo": view.get("demo"),
    }


def admin_farm_view(row: dict, owner_private: bool) -> dict:
    """Gym-style user row, farm-shaped. Private farms hide email, phone, address, listings."""
    out = {
        "id": row.get("id"),
        "name": row.get("name"),
        "type": row.get("type"),
        "is_unclaimed": row.get("is_unclaimed"),
        "claimed_at": row.get("claimed_at"),
        "created_at": row.get("created_at"),
        "listing_count": row.get("listing_count") or 0,
        "demo_count": row.get("demo_count") or 0,
        "claim_pending": row.get("claim_pending"),
        "private": bool(owner_private),
        "owner_id": row.get("owner_id") or "",
        "owner_name": row.get("owner_name") or "",
        "owner_disabled": bool(row.get("owner_disabled")),
        "last_sync_at": row.get("last_sync_at"),
        "lat": row.get("lat"),
        "lng": row.get("lng"),
    }
    if owner_private:
        out["owner_email"] = ""
        out["owner_phone"] = ""
        out["description"] = ""
        out["claim_id"] = ""
        out["listings"] = [admin_listing_view(l) for l in (row.get("listings") or [])]
        out["claim_pending_email"] = ""
    else:
        out["owner_email"] = row.get("owner_email") or ""
        out["owner_phone"] = row.get("owner_phone") or ""
        out["description"] = row.get("description") or ""
        out["claim_id"] = row.get("claim_id") or ""
        out["listings"] = row.get("listings") or []
        out["claim_pending_name"] = row.get("claim_pending_name") or ""
        out["claim_pending_email"] = row.get("claim_pending_email") or ""
        out["claim_pending_user_id"] = row.get("claim_pending_user_id") or ""
    return out
