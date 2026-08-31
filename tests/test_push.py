from unittest.mock import MagicMock, patch

from app.models.push_subscription import PushSubscription
from app.services import webpush as push_svc


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, email, name, role, pw="pass", phone=""):
    resp = client.post("/auth/register", json={
        "email": email, "password": pw, "name": name, "role": role, "phone": phone,
    })
    assert resp.status_code == 201, resp.text
    return client.post("/auth/token", data={"username": email, "password": pw}).json()["access_token"]


def _listing(client, farmer_headers):
    node = client.post("/nodes", json={
        "name": "Beds", "type": "hobby_farm", "lat": 60.52, "lng": 24.75,
    }, headers=farmer_headers).json()
    stall = client.post("/stalls", json={
        "node_id": node["id"],
        "available_from": "2026-08-22T10:00:00",
        "available_until": "2026-08-22T14:00:00",
        "pickup_point": "gate",
        "lots": [{"produce_name": "Milk", "quantity_kg": 10, "unit": "L"}],
    }, headers=farmer_headers).json()
    return stall["lots"][0]["id"]


def test_vapid_public_key_is_uncompressed_point(client):
    resp = client.get("/push/vapid-public")
    assert resp.status_code == 200
    key = resp.json()["public_key"]
    assert isinstance(key, str) and len(key) > 80
    import base64
    from pathlib import Path
    pad = "=" * ((4 - len(key) % 4) % 4)
    raw = base64.urlsafe_b64decode(key + pad)
    assert raw[0] == 4
    assert len(raw) == 65
    stored = Path("data/vapid.json")
    if stored.is_file():
        assert "BEGIN" not in stored.read_text(encoding="utf-8")


def test_subscribe_upsert_and_unsubscribe(client, db):
    token = _token(client, "push-user@t.fi", "Anna", "buyer")
    payload = {
        "endpoint": "https://web.push.apple.com/test-endpoint-1",
        "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
    }
    created = client.post("/push/subscribe", json=payload, headers=_auth(token))
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "subscribed"
    assert db.query(PushSubscription).count() == 1

    other = _token(client, "push-other@t.fi", "Pekka", "farmer")
    moved = client.post("/push/subscribe", json=payload, headers=_auth(other))
    assert moved.status_code == 200
    rows = db.query(PushSubscription).all()
    assert len(rows) == 1
    owner = client.get("/auth/me", headers=_auth(other)).json()
    assert rows[0].user_id == owner["id"]

    gone = client.request(
        "DELETE", "/push/subscribe",
        json={"endpoint": payload["endpoint"]},
        headers=_auth(other),
    )
    assert gone.status_code == 200
    assert db.query(PushSubscription).count() == 0


def test_subscribe_rejects_non_https(client):
    token = _token(client, "push-bad@t.fi", "Anna", "buyer")
    bad = client.post("/push/subscribe", json={
        "endpoint": "http://evil.example/push",
        "keys": {"p256dh": "x", "auth": "y"},
    }, headers=_auth(token))
    assert bad.status_code == 400


def test_create_ask_sends_web_push_to_farmer(client, monkeypatch):
    sent = []

    def fake_send(db, user_id, title="Satokori", body="", tag="satokori", url="/"):
        sent.append({"user_id": user_id, "title": title, "body": body, "tag": tag})
        return 1

    monkeypatch.setattr(push_svc, "send_to_user", fake_send)
    farmer = _token(client, "push-farmer@t.fi", "Maija", "farmer")
    buyer = _token(client, "push-buyer@t.fi", "Anna", "buyer")
    farmer_id = client.get("/auth/me", headers=_auth(farmer)).json()["id"]
    listing_id = _listing(client, _auth(farmer))
    asked = client.post("/asks", json={"listing_id": listing_id, "quantity": 2},
                        headers=_auth(buyer))
    assert asked.status_code == 201, asked.text
    assert any(p["user_id"] == farmer_id and p["title"] == "Pickup request" for p in sent)
    assert any("asked for" in p["body"] for p in sent)

    sent.clear()
    buyer_id = client.get("/auth/me", headers=_auth(buyer)).json()["id"]
    replied = client.post(
        f"/asks/{asked.json()['id']}/reply",
        json={"when_text": "la 10"},
        headers=_auth(farmer),
    )
    assert replied.status_code == 200
    assert any(p["user_id"] == buyer_id and p["title"] == "Farmer replied" for p in sent)
    assert any("la 10" in p["body"] for p in sent)


def test_send_to_user_drops_expired_subscription(db, monkeypatch):
    from app.models.user import User, UserRole
    from app.services.auth_service import hash_password
    import pywebpush

    user = User(
        id="user-push-1", email="sub@t.fi", hashed_password=hash_password("pass"),
        name="Sub", role=UserRole.buyer,
    )
    row = PushSubscription(
        id="sub-1", user_id=user.id,
        endpoint="https://web.push.apple.com/expired",
        p256dh="p", auth_key="a",
    )
    db.add_all([user, row])
    db.commit()

    def boom(*args, **kwargs):
        exc = pywebpush.WebPushException("gone")
        exc.response = MagicMock(status_code=410)
        raise exc

    monkeypatch.setattr(pywebpush, "webpush", boom)
    n = push_svc.send_to_user(db, user.id, title="Satokori", body="hello")
    assert n == 0
    assert db.query(PushSubscription).count() == 0
