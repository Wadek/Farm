from datetime import datetime, timedelta


def _register(client, email, name, role, pw="pass", phone=""):
    payload = {"email": email, "password": pw, "name": name, "role": role}
    if phone:
        payload["phone"] = phone
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    token = client.post("/auth/token", data={"username": email, "password": pw})
    return token.json()["access_token"], resp.json()["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _window():
    start = datetime.now().replace(microsecond=0) + timedelta(days=2, hours=2)
    end = start + timedelta(minutes=30)
    return start.isoformat(), end.isoformat()


def test_organizer_opens_ring_and_drop(client):
    admin, _ = _register(client, "ring-admin@test.com", "Admin", "organizer")
    start, end = _window()
    resp = client.post("/rings", json={
        "name": "REKO Rajamäki–Hyvinkää",
        "place": "S-market Rajamäki lot",
        "lat": 60.5277,
        "lng": 24.7512,
        "notes": "Cash or MobilePay",
        "starts_at": start,
        "ends_at": end,
    }, headers=_auth(admin))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["ring_name"] == "REKO Rajamäki–Hyvinkää"
    assert body["place"] == "S-market Rajamäki lot"
    assert body["offer_count"] == 0
    public = client.get("/rings").json()
    assert public["next_drop"]["id"] == body["id"]
    assert public["rings"][0]["name"] == "REKO Rajamäki–Hyvinkää"


def test_farmer_posts_lots_to_drop_and_catalog_groups_them(client):
    admin, _ = _register(client, "drop-admin@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "drop-farmer@test.com", "Niina", "farmer")
    start, end = _window()
    drop = client.post("/rings", json={
        "name": "REKO Test",
        "place": "Lot A",
        "lat": 60.55,
        "lng": 24.70,
        "starts_at": start,
        "ends_at": end,
    }, headers=_auth(admin)).json()
    node = client.post("/nodes", json={
        "name": "Toikantila", "type": "farm", "lat": 60.50, "lng": 24.76,
    }, headers=_auth(farmer)).json()
    stall = client.post("/stalls", json={
        "node_id": node["id"],
        "drop_id": drop["id"],
        "pickup_point": "ignored",
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 8,
                  "price_per_kg": 1.4, "unit": "L"}],
    }, headers=_auth(farmer))
    assert stall.status_code == 201, stall.text
    lot = stall.json()["lots"][0]
    assert lot["drop"]["id"] == drop["id"]
    assert lot["drop"]["place"] == "Lot A"
    assert lot["perpetual"] is False
    catalog = client.get("/catalog").json()["items"]
    assert catalog[0]["produce_name"] == "Raw milk"
    assert catalog[0]["drop"]["ring_name"] == "REKO Test"
    assert catalog[0]["drop"]["ring_id"]


def test_customer_orders_drop_offer_without_a_time(client):
    admin, _ = _register(client, "ord-admin@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "ord-farmer@test.com", "Niina", "farmer")
    buyer, _ = _register(client, "ord-buyer@test.com", "Anna", "buyer")
    start, end = _window()
    drop = client.post("/rings", json={
        "name": "REKO Test",
        "place": "Lot A",
        "lat": 60.55,
        "lng": 24.70,
        "starts_at": start,
        "ends_at": end,
    }, headers=_auth(admin)).json()
    node = client.post("/nodes", json={
        "name": "Toikantila", "type": "farm", "lat": 60.50, "lng": 24.76,
    }, headers=_auth(farmer)).json()
    listing_id = client.post("/stalls", json={
        "node_id": node["id"],
        "drop_id": drop["id"],
        "pickup_point": "Lot A",
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 8,
                  "price_per_kg": 1.4, "unit": "L"}],
    }, headers=_auth(farmer)).json()["lots"][0]["id"]
    asked = client.post("/asks", json={"listing_id": listing_id, "quantity": 2, "note": "2 L"},
                        headers=_auth(buyer))
    assert asked.status_code == 201, asked.text
    assert asked.json()["drop"]["place"] == "Lot A"
    confirmed = client.post(
        f"/asks/{asked.json()['id']}/reply",
        json={"when_text": ""},
        headers=_auth(farmer),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert "Lot A" in confirmed.json()["offer_text"] or confirmed.json()["offer_text"]


def test_farm_gate_still_needs_a_time(client):
    farmer, _ = _register(client, "gate-farmer@test.com", "Maija", "farmer")
    buyer, _ = _register(client, "gate-buyer@test.com", "Anna", "buyer")
    node = client.post("/nodes", json={
        "name": "Beds", "type": "hobby_farm", "lat": 60.52, "lng": 24.75,
    }, headers=_auth(farmer)).json()
    listing_id = client.post("/stalls", json={
        "node_id": node["id"],
        "available_from": "2026-09-10T10:00:00",
        "available_until": "2026-09-10T14:00:00",
        "pickup_point": "gate",
        "lots": [{"produce_name": "Kale", "quantity_kg": 4, "price_per_kg": 3, "perpetual": True}],
    }, headers=_auth(farmer)).json()["lots"][0]["id"]
    asked = client.post("/asks", json={"listing_id": listing_id, "quantity": 1},
                        headers=_auth(buyer)).json()
    missing = client.post(f"/asks/{asked['id']}/reply", json={"when_text": ""}, headers=_auth(farmer))
    assert missing.status_code == 400
    ok = client.post(f"/asks/{asked['id']}/reply", json={"when_text": "la 10"}, headers=_auth(farmer))
    assert ok.status_code == 200
    assert ok.json()["offer_text"] == "la 10"


def test_catalog_keeps_drop_place_when_farm_also_has_a_gate_lot(client):
    admin, _ = _register(client, "mix-admin@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "mix-farmer@test.com", "Niina", "farmer")
    start, end = _window()
    drop = client.post("/rings", json={
        "name": "REKO Mix", "place": "Lot A", "lat": 60.55, "lng": 24.70,
        "starts_at": start, "ends_at": end,
    }, headers=_auth(admin)).json()
    node = client.post("/nodes", json={
        "name": "Toikantila", "type": "farm", "lat": 60.50, "lng": 24.76,
        "description": "Pirttimäentie 178",
    }, headers=_auth(farmer)).json()
    client.post("/stalls", json={
        "node_id": node["id"],
        "drop_id": drop["id"],
        "pickup_point": "ignored",
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 8,
                  "price_per_kg": 1.4, "unit": "L"}],
    }, headers=_auth(farmer))
    client.post("/stalls", json={
        "node_id": node["id"],
        "pickup_point": "Pirttimäentie 178",
        "lots": [{"produce_name": "Hay", "category": "feed", "quantity_kg": 20,
                  "price_per_kg": 0.2, "unit": "kg", "perpetual": True}],
    }, headers=_auth(farmer))
    catalog = client.get("/catalog").json()["items"]
    drop_item = next(i for i in catalog if i.get("drop") and i["produce_name"] == "Raw milk")
    gate_item = next(i for i in catalog if not i.get("drop") and i["produce_name"] == "Hay")
    assert drop_item["pickup_point"] == "Lot A"
    assert gate_item["pickup_point"] == "Pirttimäentie 178"


def test_drop_order_sms_and_inbox_include_the_ring(client):
    admin, _ = _register(client, "sms-admin@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "sms-farmer@test.com", "Niina", "farmer", phone="+358442104990")
    buyer, _ = _register(client, "sms-buyer@test.com", "Anna", "buyer", phone="+358403333333")
    start, end = _window()
    drop = client.post("/rings", json={
        "name": "REKO Test", "place": "Lot A", "lat": 60.55, "lng": 24.70,
        "starts_at": start, "ends_at": end,
    }, headers=_auth(admin)).json()
    node = client.post("/nodes", json={
        "name": "Toikantila", "type": "farm", "lat": 60.50, "lng": 24.76,
    }, headers=_auth(farmer)).json()
    listing_id = client.post("/stalls", json={
        "node_id": node["id"],
        "drop_id": drop["id"],
        "pickup_point": "Lot A",
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 8,
                  "price_per_kg": 1.4, "unit": "L"}],
    }, headers=_auth(farmer)).json()["lots"][0]["id"]
    asked = client.post("/asks", json={"listing_id": listing_id, "quantity": 2, "note": "2 L"},
                        headers=_auth(buyer))
    assert asked.status_code == 201, asked.text
    inbox = client.get("/asks", headers=_auth(farmer)).json()
    assert inbox[0]["drop"]["place"] == "Lot A"
    logs = client.get("/sms", headers=_auth(admin)).json()
    assert any("REKO-jakoon" in row["body"] for row in logs)
    page = client.get(f"/r/{asked.json()['token']}")
    assert page.status_code == 200
    public = client.post(
        f"/asks/public/{asked.json()['token']}/reply",
        json={"when_text": ""},
    )
    assert public.status_code == 200, public.text
    assert public.json()["status"] == "confirmed"
    assert "Lot A" in (public.json()["offer_text"] or "")


def test_ring_admin_claims_unclaimed_ring_and_opens_a_drop(client):
    admin, _ = _register(client, "ra-admin@test.com", "Admin", "organizer")
    manager, _ = _register(client, "ra-manager@test.com", "Maija", "ring_admin")
    buyer, _ = _register(client, "ra-buyer@test.com", "Anna", "buyer")
    start, end = _window()
    created = client.post("/rings", json={
        "name": "REKO Hyvinkää", "place": "Lot A", "lat": 60.63, "lng": 24.86,
        "starts_at": start, "ends_at": end,
        "facebook_url": "https://www.facebook.com/groups/hyvinkaanreko",
    }, headers=_auth(admin)).json()
    ring_id = created["ring_id"]
    denied = client.post(f"/rings/{ring_id}/claim", json={}, headers=_auth(buyer))
    assert denied.status_code == 403
    claimed = client.post(f"/rings/{ring_id}/claim", json={}, headers=_auth(manager))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["is_unclaimed"] is False
    assert claimed.json()["admin_name"] == "Maija"
    later_start, later_end = _window()
    drop = client.post(f"/rings/{ring_id}/drops", json={
        "starts_at": later_start, "ends_at": later_end,
    }, headers=_auth(manager))
    assert drop.status_code == 201, drop.text
    public = client.get("/rings").json()
    assert any(r["id"] == ring_id and r["facebook_url"].endswith("hyvinkaanreko") for r in public["rings"])


def test_catalog_drop_items_carry_ring_id_for_location_filter(client):
    admin, _ = _register(client, "loc-admin@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "loc-farmer@test.com", "Niina", "farmer")
    start, end = _window()
    hy = client.post("/rings", json={
        "name": "Hyvinkään Farmarin Markkinat / REKO",
        "place": "Mäkikuumolantie 3, Hyvinkää",
        "lat": 60.63, "lng": 24.86,
        "starts_at": start, "ends_at": end,
    }, headers=_auth(admin)).json()
    nj = client.post("/rings", json={
        "name": "REKO Nurmijärvi",
        "place": "Nurmijärven kirkonkylä",
        "lat": 60.46, "lng": 24.80,
        "starts_at": start, "ends_at": end,
    }, headers=_auth(admin)).json()
    node = client.post("/nodes", json={
        "name": "Toikantila", "type": "farm", "lat": 60.50, "lng": 24.76,
    }, headers=_auth(farmer)).json()
    client.post("/stalls", json={
        "node_id": node["id"], "drop_id": hy["id"], "pickup_point": "lot",
        "lots": [{"produce_name": "Milk", "category": "dairy", "quantity_kg": 4,
                  "price_per_kg": 1.4, "unit": "L"}],
    }, headers=_auth(farmer))
    client.post("/stalls", json={
        "node_id": node["id"], "drop_id": nj["id"], "pickup_point": "lot",
        "lots": [{"produce_name": "Eggs", "category": "eggs", "quantity_kg": 12,
                  "price_per_kg": 0.4, "unit": "kpl"}],
    }, headers=_auth(farmer))
    items = client.get("/catalog").json()["items"]
    drops = [i for i in items if i.get("drop")]
    ring_ids = {i["drop"]["ring_id"] for i in drops}
    assert hy["ring_id"] in ring_ids
    assert nj["ring_id"] in ring_ids
    by_hy = [i["produce_name"] for i in drops if i["drop"]["ring_id"] == hy["ring_id"]]
    by_nj = [i["produce_name"] for i in drops if i["drop"]["ring_id"] == nj["ring_id"]]
    assert "Milk" in by_hy
    assert "Eggs" in by_nj
    assert "Eggs" not in by_hy
    html = client.get("/").text
    assert 'filterCat === "reko"' in html
    assert "filterReko" in html
    assert "data-ring" in html


def test_buyer_cannot_create_a_ring(client):
    buyer, _ = _register(client, "ring-buyer@test.com", "Anna", "buyer")
    start, end = _window()
    resp = client.post("/rings", json={
        "name": "Nope", "place": "x", "lat": 60.5, "lng": 24.7,
        "starts_at": start, "ends_at": end,
    }, headers=_auth(buyer))
    assert resp.status_code == 403
