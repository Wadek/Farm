from datetime import datetime, timedelta, timezone

from app.models import Node


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
    body = {
        "node_id": node_id,
        "pickup_point": pickup,
        "lots": lots,
    }
    if any(not lot.get("perpetual") for lot in lots):
        body["available_from"] = available_from
        body["available_until"] = available_until
    return client.post("/stalls", json=body, headers=_auth(token))


def test_catalog_featured_first_then_latest_farm(client, db):
    admin, _ = _register(client, "admin-feat@test.com", "Admin", "organizer")
    older, _ = _register(client, "old-farm@test.com", "Older", "farmer")
    newer, _ = _register(client, "new-farm@test.com", "Newer", "farmer")

    old_node = client.post("/nodes", json={
        "name": "Older Farm", "type": "farm", "lat": 60.55, "lng": 24.70,
    }, headers=_auth(older)).json()
    new_node = client.post("/nodes", json={
        "name": "Newer Farm", "type": "farm", "lat": 60.56, "lng": 24.71,
    }, headers=_auth(newer)).json()

    old_lot = _open_stall(client, older, old_node["id"], [
        {"produce_name": "Hay", "category": "feed", "quantity_kg": 10, "price_per_kg": 0.2, "perpetual": True},
        {"produce_name": "Kale", "category": "greens", "quantity_kg": 4, "price_per_kg": 3.0, "perpetual": True},
    ]).json()["lots"]
    new_lot = _open_stall(client, newer, new_node["id"], [
        {"produce_name": "Milk", "category": "dairy", "quantity_kg": 8, "price_per_kg": 1.4,
         "unit": "L", "perpetual": True},
    ]).json()["lots"]

    past = datetime.now(timezone.utc) - timedelta(days=5)
    recent = datetime.now(timezone.utc)
    db.query(Node).filter(Node.id == old_node["id"]).update({"created_at": past})
    db.query(Node).filter(Node.id == new_node["id"]).update({"created_at": recent})
    db.commit()

    featured_id = old_lot[0]["id"]
    resp = client.post("/admin/featured", json={"listing_id": featured_id}, headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    assert resp.json()["featured"]["id"] == featured_id
    assert resp.json()["featured"]["featured"] is True

    catalog = client.get("/catalog").json()["items"]
    names = [i["produce_name"] for i in catalog]
    assert names[0] == "Hay"
    assert catalog[0]["featured"] is True
    assert catalog[0]["farm_name"] == "Older Farm"
    rest_farms = [i["farm_name"] for i in catalog[1:]]
    assert rest_farms[0] == "Newer Farm"
    assert "Milk" in names


def test_demo_listings_are_flagged(client):
    token, _ = _register(client, "demo-farm@test.com", "Demo Farmer", "farmer")
    node = client.post("/nodes", json={
        "name": "Demo Beds", "type": "hobby_farm", "lat": 60.55, "lng": 24.70,
    }, headers=_auth(token)).json()
    stall = _open_stall(client, token, node["id"], [
        {"produce_name": "Eggs", "category": "eggs", "quantity_kg": 12, "price_per_kg": 0.4,
         "unit": "kpl", "perpetual": True, "demo": True},
    ])
    assert stall.status_code == 201, stall.text
    assert stall.json()["lots"][0]["demo"] is True
    catalog = client.get("/catalog").json()
    assert catalog["items"][0]["demo"] is True
    assert catalog["items"][0]["produce_name"] == "Eggs"


def test_farmer_claims_unclaimed_farm_by_node_id(client):
    admin, _ = _register(client, "claim-admin2@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "real-farmer@test.com", "Niina", "farmer")
    farm = client.post("/onboard", json={
        "farmer_name": "Placeholder",
        "farm_name": "Toikantila",
        "pickup_point": "Pirttimäentie 178",
        "lat": 60.5084,
        "lng": 24.7616,
    }, headers=_auth(admin)).json()
    claimed = client.post("/nodes/claim", json={"node_id": farm["node_id"]}, headers=_auth(farmer))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "pending"
    assert claimed.json()["claimed_at"] is None
    assert client.get("/nodes", headers=_auth(farmer)).json() == []
    square = client.get("/square").json()
    stall = next(s for s in square["stalls"] if s["farm_name"] == "Toikantila")
    assert stall["is_unclaimed"] is True
    assert stall["claim_pending"] is True
    overview = client.get("/admin/overview", headers=_auth(admin)).json()
    assert overview["pending_claims"]
    approved = client.post("/admin/claims", json={"node_id": farm["node_id"], "approve": True}, headers=_auth(admin))
    assert approved.status_code == 200, approved.text
    square = client.get("/square").json()
    stall = next(s for s in square["stalls"] if s["farm_name"] == "Toikantila")
    assert stall["is_unclaimed"] is False
    assert stall["farmer_name"] == "Niina"


def test_admin_overview_lists_farms(client):
    admin, _ = _register(client, "overview-admin@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "overview-farmer@test.com", "Maija", "farmer")
    client.post("/onboard", json={
        "farmer_name": "Open",
        "farm_name": "Open Farm",
        "pickup_point": "gate",
        "lat": 60.5,
        "lng": 24.7,
    }, headers=_auth(admin))
    node = client.post("/nodes", json={
        "name": "Claimed Farm", "type": "farm", "lat": 60.55, "lng": 24.70,
    }, headers=_auth(farmer)).json()
    _open_stall(client, farmer, node["id"], [
        {"produce_name": "Kale", "quantity_kg": 2, "price_per_kg": 4, "perpetual": True, "demo": True},
    ])

    forbidden = client.get("/admin/overview", headers=_auth(farmer))
    assert forbidden.status_code == 403

    overview = client.get("/admin/overview", headers=_auth(admin)).json()
    names = {f["name"] for f in overview["farms"]}
    assert "Open Farm" in names
    assert "Claimed Farm" in names
    assert overview["farm_count"] == 2
    assert overview["unclaimed_count"] == 1
    assert overview["demo_count"] >= 1
    assert overview["featured"] is None


def test_admin_can_clear_featured(client):
    admin, _ = _register(client, "clear-feat@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "clear-farm@test.com", "Farmer", "farmer")
    node = client.post("/nodes", json={
        "name": "Feat Farm", "type": "farm", "lat": 60.55, "lng": 24.70,
    }, headers=_auth(farmer)).json()
    listing_id = _open_stall(client, farmer, node["id"], [
        {"produce_name": "Milk", "quantity_kg": 2, "price_per_kg": 1.4, "perpetual": True},
    ]).json()["lots"][0]["id"]
    client.post("/admin/featured", json={"listing_id": listing_id}, headers=_auth(admin))
    cleared = client.post("/admin/featured", json={"listing_id": None}, headers=_auth(admin))
    assert cleared.status_code == 200
    assert cleared.json()["featured"] is None
    catalog = client.get("/catalog").json()["items"]
    assert catalog[0]["featured"] is False


def test_ask_on_unclaimed_demo_goes_to_organizer(client):
    admin, admin_id = _register(client, "ask-admin@test.com", "Admin", "organizer")
    buyer, _ = _register(client, "ask-buyer@test.com", "Anna", "buyer")
    farm = client.post("/onboard", json={
        "farmer_name": "Placeholder",
        "farm_name": "Unclaimed Dairy",
        "pickup_point": "gate",
        "lat": 60.5,
        "lng": 24.7,
        "available_from": _window()[0],
        "available_until": _window()[1],
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 10,
                  "price_per_kg": 1.4, "unit": "L"}],
    }, headers=_auth(admin)).json()
    listing_id = farm["lots"][0]["id"]
    asked = client.post("/asks", json={"listing_id": listing_id, "quantity": 2}, headers=_auth(buyer))
    assert asked.status_code == 201, asked.text
    assert asked.json()["farmer_id"] == admin_id
    inbox = client.get("/asks", headers=_auth(admin)).json()
    assert any(a["id"] == asked.json()["id"] for a in inbox)


def test_admin_routes_reject_anonymous_and_farmers(client):
    farmer, _ = _register(client, "sec-farmer@test.com", "Niina", "farmer")
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/admin/overview").status_code in (401, 403)
    assert client.post("/admin/claims", json={"node_id": "n1", "approve": True}).status_code in (401, 403)
    assert client.post("/admin/featured", json={"listing_id": None}).status_code in (401, 403)
    assert client.get("/admin/overview", headers=_auth(farmer)).status_code == 403
    assert client.post("/admin/claims", json={"node_id": "n1", "approve": True}, headers=_auth(farmer)).status_code == 403
