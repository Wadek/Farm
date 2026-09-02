from app.services.privacy import (
    generate_recovery_key, encrypt_json, decrypt_json, unb64u,
    is_sealed, admin_listing_view, admin_farm_view,
)


def _register(client, email, name, role, pw="pass"):
    resp = client.post("/auth/register", json={
        "email": email, "password": pw, "name": name, "role": role, "phone": "0401234567",
    })
    assert resp.status_code == 201, resp.text
    token = client.post("/auth/token", data={"username": email, "password": pw})
    return token.json()["access_token"], resp.json()["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_aes_gcm_round_trip_hides_plaintext():
    key = generate_recovery_key()
    assert len(unb64u(key)) == 32
    env = encrypt_json({"produce_name": "secret kale", "phone": "0401234567"}, key)
    blob = env["iv"] + env["ct"]
    assert "secret kale" not in blob
    assert "0401234567" not in blob
    opened = decrypt_json(env["iv"], env["ct"], key)
    assert opened["produce_name"] == "secret kale"
    other = generate_recovery_key()
    try:
        decrypt_json(env["iv"], env["ct"], other)
        assert False, "wrong key should fail"
    except Exception:
        pass


def test_admin_view_of_sealed_listing_has_no_harvest():
    view = admin_listing_view({
        "id": "l1", "node_id": "n1", "private": True,
        "produce_name": "secret kale", "quantity_kg": 8, "price_per_kg": 4,
        "pickup_point": "Red shed", "category": "greens", "status": "active",
        "node_name": "Toikantila", "lockbox": {"iv": "aaa", "ct": "SECRET"},
    })
    blob = str(view)
    assert view["private"] is True
    assert view["produce_name"] is None
    assert view["pickup_point"] is None
    assert "secret kale" not in blob
    assert "Red shed" not in blob
    assert "SECRET" not in blob


def test_farmer_privacy_hides_phone_from_admin(client):
    admin, _ = _register(client, "priv-admin@test.com", "Admin", "organizer")
    farmer, fid = _register(client, "priv-farmer@test.com", "Niina", "farmer")
    key = generate_recovery_key()
    box = encrypt_json({"phone": "0401234567", "name": "Niina"}, key)
    locked = client.post("/auth/privacy", json={"privacy": True, "lockbox": {"v": 1, **box}}, headers=_auth(farmer))
    assert locked.status_code == 200, locked.text
    me = client.get("/auth/me", headers=_auth(farmer)).json()
    assert me["privacy"] is True
    assert me["phone"] == ""
    node = client.post("/nodes", json={
        "name": "Niina Beds", "type": "hobby_farm", "lat": 60.55, "lng": 24.70,
        "description": "Red shed behind the barn",
    }, headers=_auth(farmer)).json()
    stall = client.post("/stalls", json={
        "node_id": node["id"],
        "pickup_point": "Red shed behind the barn",
        "lots": [{
            "produce_name": "secret kale", "category": "greens", "quantity_kg": 4,
            "price_per_kg": 3, "perpetual": True, "private": True,
            "lockbox": {"v": 1, **encrypt_json({"produce_name": "secret kale"}, key)},
        }],
    }, headers=_auth(farmer))
    assert stall.status_code == 201, stall.text
    overview = client.get("/admin/overview", headers=_auth(admin)).json()
    farm = next(f for f in overview["farms"] if f["name"] == "Niina Beds")
    assert farm["private"] is True
    assert farm["owner_email"] == ""
    assert farm["owner_phone"] == ""
    assert "Red shed" not in (farm.get("description") or "")
    listed = [l for l in overview["listings"] if l.get("node_id") == node["id"]]
    assert listed
    assert listed[0]["private"] is True
    assert listed[0]["produce_name"] is None
    blob = str(overview)
    assert "0401234567" not in blob
    catalog = client.get("/catalog").json()["items"]
    kale = next(i for i in catalog if i["node_id"] == node["id"])
    assert kale["private"] is True
    assert kale["produce_name"] == "secret kale"
    assert kale["pickup_point"] == ""


def test_disabled_account_cannot_login(client):
    admin, _ = _register(client, "dis-admin@test.com", "Admin", "organizer")
    farmer, fid = _register(client, "dis-farmer@test.com", "Niina", "farmer")
    resp = client.post("/admin/users/disable", json={"user_id": fid, "disabled": True}, headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    denied = client.post("/auth/token", data={"username": "dis-farmer@test.com", "password": "pass"})
    assert denied.status_code == 403


def test_privacy_js_and_settings_copy_ship():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    boot = (root / "static" / "privacy.js").read_text(encoding="utf-8")
    html = (root / "static" / "square.html").read_text(encoding="utf-8")
    fi = (root / "static" / "locales" / "fi.json").read_text(encoding="utf-8")
    assert "AES-GCM" in boot
    assert "generateRecoveryKey" in boot
    assert "/static/privacy.js" in html
    assert "Keep my farm private" in html
    assert "data-privacy" in html
    assert "lockGlyph" in html
    assert "Private lockbox" in fi
    assert is_sealed({"private": True, "v": 1, "iv": "a", "ct": "b"})
    farm = admin_farm_view({
        "id": "n1", "name": "X", "owner_email": "a@b.c", "owner_phone": "040",
        "description": "secret", "listings": [{"private": True, "produce_name": "kale", "id": "l"}],
        "listing_count": 1, "is_unclaimed": False, "owner_name": "Niina",
    }, True)
    assert farm["owner_email"] == ""
    assert farm["listings"][0]["produce_name"] is None
