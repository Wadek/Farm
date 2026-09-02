from datetime import datetime, timedelta


def _register(client, email, name, role, pw="pass"):
    resp = client.post("/auth/register", json={
        "email": email, "password": pw, "name": name, "role": role,
    })
    assert resp.status_code == 201, resp.text
    token = client.post("/auth/token", data={"username": email, "password": pw})
    return token.json()["access_token"], resp.json()["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _window():
    start = datetime.now().replace(microsecond=0) + timedelta(hours=2)
    end = start + timedelta(hours=4)
    return start.isoformat(), end.isoformat()


def _open_stall(client, token, node_id, lots, pickup="Farm gate"):
    available_from, available_until = _window()
    return client.post("/stalls", json={
        "node_id": node_id,
        "available_from": available_from,
        "available_until": available_until,
        "pickup_point": pickup,
        "lots": lots,
    }, headers=_auth(token))


def test_open_stall_and_browse_square(client):
    token, _ = _register(client, "farmer@test.com", "Farmer", "farmer")
    node = client.post("/nodes", json={
        "name": "Test Farm", "type": "hobby_farm",
        "lat": 60.5522, "lng": 24.7050,
    }, headers=_auth(token)).json()

    resp = _open_stall(client, token, node["id"], [
        {"produce_name": "Kale", "category": "greens", "quantity_kg": 8, "price_per_kg": 4.0},
        {"produce_name": "Eggs", "category": "eggs", "quantity_kg": 2, "price_per_kg": 6.0},
    ])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["farm_name"] == "Test Farm"
    assert len(body["lots"]) == 2
    assert body["lots"][0]["available_from"] is not None

    square = client.get("/square").json()
    assert square["stall_count"] == 1
    assert square["lot_count"] == 2
    stall = square["stalls"][0]
    assert stall["farm_name"] == "Test Farm"
    assert stall["pickup_point"] == "Farm gate"
    names = {g["produce_name"] for g in stall["goods"]}
    assert names == {"Kale", "Eggs"}
    assert body["lots"][0]["unit"] == "kg"


def test_remove_listing_sold_out_on_catalog_gone_from_farm_window(client):
    token, _ = _register(client, "drop-kale@test.com", "Farmer", "farmer")
    node = client.post("/nodes", json={
        "name": "Kale Farm", "type": "hobby_farm",
        "lat": 60.5522, "lng": 24.7050,
    }, headers=_auth(token)).json()
    stall = _open_stall(client, token, node["id"], [
        {"produce_name": "Kale", "category": "greens", "quantity_kg": 8, "price_per_kg": 4.0},
        {"produce_name": "Eggs", "category": "eggs", "quantity_kg": 2, "price_per_kg": 6.0},
    ]).json()
    kale = next(lot for lot in stall["lots"] if lot["produce_name"] == "Kale")
    gone = client.post(f"/listings/{kale['id']}/sold-out", headers=_auth(token))
    assert gone.status_code == 200, gone.text
    assert gone.json()["status"] == "sold_out"
    catalog = {i["produce_name"]: i for i in client.get("/catalog").json()["items"]}
    assert catalog["Kale"]["status"] == "sold_out"
    assert catalog["Eggs"]["status"] == "active"
    html = client.get("/").text
    assert "function liveGoods" in html
    assert 'g.status !== "sold_out"' in html
    assert "data-remove" in html
    assert "function refreshSellAndFarms" in html


def test_listing_unit_liters(client):
    token, _ = _register(client, "farmer@test.com", "Farmer", "farmer")
    node = client.post("/nodes", json={
        "name": "Dairy", "type": "hobby_farm",
        "lat": 60.5522, "lng": 24.7050,
    }, headers=_auth(token)).json()
    resp = _open_stall(client, token, node["id"], [
        {"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 10,
         "price_per_kg": 1.4, "unit": "L"},
    ])
    assert resp.status_code == 201, resp.text
    assert resp.json()["lots"][0]["unit"] == "L"
    catalog = client.get("/catalog").json()
    assert catalog["items"][0]["unit"] == "L"
    assert catalog["items"][0]["category"] == "dairy"


def test_square_radius_filter(client):
    token, _ = _register(client, "farmer@test.com", "Farmer", "farmer")
    node = client.post("/nodes", json={
        "name": "Test Farm", "type": "farm",
        "lat": 60.5522, "lng": 24.7050,
    }, headers=_auth(token)).json()
    _open_stall(client, token, node["id"], [
        {"produce_name": "Hay", "quantity_kg": 10, "price_per_kg": 0.2},
    ])

    near = client.get("/square?lat=60.5522&lng=24.7050&radius_km=5").json()
    assert near["stall_count"] == 1
    assert near["stalls"][0]["distance_km"] == 0.0

    far = client.get("/square?lat=60.1699&lng=24.9384&radius_km=10").json()
    assert far["stall_count"] == 0


def test_demand_flare_lights_matching_stall(client):
    farmer_token, _ = _register(client, "farmer@test.com", "Maija", "farmer")
    buyer_token, _ = _register(client, "buyer@test.com", "Anna", "buyer")
    node = client.post("/nodes", json={
        "name": "Heritage Beds", "type": "hobby_farm",
        "lat": 60.5270, "lng": 24.7500,
    }, headers=_auth(farmer_token)).json()
    _open_stall(client, farmer_token, node["id"], [
        {"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 20, "price_per_kg": 1.4},
    ])

    flare = client.post("/flares", json={
        "item": "raw milk", "quantity_note": "5 litres",
    }, headers=_auth(buyer_token))
    assert flare.status_code == 201, flare.text

    square = client.get("/square").json()
    assert square["flares"][0]["item"] == "raw milk"
    assert square["stalls"][0]["matched_flares"] == [flare.json()["id"]]
    assert square["flares"][0]["matching_stalls"] == [node["id"]]


def test_buyer_claims_lot(client):
    farmer_token, _ = _register(client, "farmer@test.com", "Wade", "farmer")
    buyer_token, _ = _register(client, "buyer@test.com", "Anna", "buyer")
    node = client.post("/nodes", json={
        "name": "Kariniemi", "type": "farm",
        "lat": 60.5522, "lng": 24.7050,
    }, headers=_auth(farmer_token)).json()
    stall = _open_stall(client, farmer_token, node["id"], [
        {"produce_name": "Kale", "quantity_kg": 8, "price_per_kg": 4.0},
    ]).json()
    listing_id = stall["lots"][0]["id"]

    claimed = client.post(f"/listings/{listing_id}/claim", json={"quantity_kg": 2},
                          headers=_auth(buyer_token))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "reserved"
    assert claimed.json()["claimed_by"] == "Anna"

    square = client.get("/square").json()
    assert square["lot_count"] == 0


def test_pending_customer_request_appears_in_ledger(client):
    farmer_token, _ = _register(client, "farmer@test.com", "Wade", "farmer")
    buyer_token, _ = _register(client, "buyer@test.com", "Anna", "buyer")
    admin_token, _ = _register(client, "admin@test.com", "Admin", "organizer")
    node = client.post("/nodes", json={
        "name": "Kariniemi", "type": "farm",
        "lat": 60.5522, "lng": 24.7050,
    }, headers=_auth(farmer_token)).json()
    stall = _open_stall(client, farmer_token, node["id"], [
        {"produce_name": "Kale", "quantity_kg": 8},
    ]).json()

    asked = client.post(
        "/asks",
        json={"listing_id": stall["lots"][0]["id"], "quantity": 2, "note": "This week"},
        headers=_auth(buyer_token),
    )
    assert asked.status_code == 201, asked.text

    ledger = client.get("/ledger", headers=_auth(admin_token))
    assert ledger.status_code == 200
    pending = next(row for row in ledger.json() if row["type"] == "request")
    assert pending["status"] == "pending"
    assert pending["from_farm"] == "Kariniemi"
    assert pending["produce"] == "Kale"
    assert pending["buyer"] == "Anna"
    assert pending["quantity_kg"] == 2


def test_unclaimed_farm_appears_on_square_without_listings(client, db):
    from app.models import Node, NodeType

    db.add(Node(
        id="node-kumpula",
        owner_id=None,
        name="Kumpula Apple Orchard",
        type=NodeType.farm,
        lat=60.5100,
        lng=24.7800,
        description="Kumpulantie 12, Hyvinkää — orchard gate.",
        area_m2=15000,
        claim_id="claim-kumpula-2026",
        claimed_at=None,
    ))
    db.commit()

    square = client.get("/square").json()
    stall = next(s for s in square["stalls"] if s["node_id"] == "node-kumpula")
    assert stall["is_unclaimed"] is True
    assert stall["farmer_name"] == "Unclaimed"
    assert stall["farm_name"] == "Kumpula Apple Orchard"
    assert stall["claim_id"] == "claim-kumpula-2026"
    assert stall["description"].startswith("Kumpulantie")
    assert stall["goods"] == []


def test_farmer_only_open_stall(client):
    token, _ = _register(client, "buyer@test.com", "Anna", "buyer")
    resp = client.post("/stalls", json={
        "node_id": "nope",
        "available_from": _window()[0],
        "available_until": _window()[1],
        "pickup_point": "gate",
        "lots": [{"produce_name": "Kale", "quantity_kg": 1}],
    }, headers=_auth(token))
    assert resp.status_code == 403
