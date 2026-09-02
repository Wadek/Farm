from datetime import datetime, timedelta


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _token(client, email, name, role, pw="pass"):
    client.post("/auth/register", json={
        "email": email, "password": pw, "name": name, "role": role,
    })
    return client.post("/auth/token", data={"username": email, "password": pw}).json()["access_token"]


def _window():
    start = datetime.now().replace(microsecond=0) + timedelta(hours=2)
    end = start + timedelta(hours=4)
    return start.isoformat(), end.isoformat()


def test_organizer_onboards_farm_in_one_visit(client):
    token = _token(client, "wade@test.com", "Wade", "organizer")
    start, end = _window()
    resp = client.post("/onboard", json={
        "farmer_name": "Maija Niemi",
        "farm_name": "Rajamäki Beds",
        "pickup_point": "Red shed",
        "lat": 60.5270,
        "lng": 24.7500,
        "phone": "0401234567",
        "available_from": start,
        "available_until": end,
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 10, "price_per_kg": 1.4}],
    }, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["farmer_name"] == "Maija Niemi"
    assert body["email"].endswith("@satokori.local")
    assert body["password"]
    assert len(body["lots"]) == 1

    login = client.post("/auth/token", data={"username": body["email"], "password": body["password"]})
    assert login.status_code == 200

    catalog = client.get("/catalog").json()
    assert catalog["count"] == 1
    assert catalog["items"][0]["produce_name"] == "Raw milk"
    assert catalog["items"][0]["farm_name"] == "Rajamäki Beds"


def test_farmer_self_onboards_farm_without_claim_code(client):
    farmer = _token(client, "self-farm@test.com", "Maija", "farmer")
    node = client.post("/nodes", json={
        "name": "Maija Beds", "type": "hobby_farm",
        "lat": 60.53, "lng": 24.74, "description": "Red shed",
    }, headers=_auth(farmer))
    assert node.status_code == 201, node.text
    body = node.json()
    assert body["name"] == "Maija Beds"
    assert body["claimed_at"]
    square = client.get("/square").json()
    stall = next(s for s in square["stalls"] if s["farm_name"] == "Maija Beds")
    assert stall["is_unclaimed"] is False
    assert stall["farmer_name"] == "Maija"


def test_organizer_can_claim_unclaimed_farm(client):
    admin = _token(client, "claim-org@test.com", "Admin", "organizer")
    farm = client.post("/onboard", json={
        "farmer_name": "Placeholder",
        "farm_name": "Org Claim Farm",
        "pickup_point": "gate",
        "lat": 60.5, "lng": 24.7,
    }, headers=_auth(admin)).json()
    claimed = client.post("/nodes/claim", json={"claim_id": farm["claim_id"]}, headers=_auth(admin))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["farm_name"] == "Org Claim Farm"


def test_buyer_cannot_onboard(client):
    token = _token(client, "anna@test.com", "Anna", "buyer")
    resp = client.post("/onboard", json={
        "farmer_name": "X", "farm_name": "Y", "pickup_point": "gate",
        "lat": 60.5, "lng": 24.7,
    }, headers=_auth(token))
    assert resp.status_code == 403


def test_farmer_claims_onboarded_farm(client):
    admin = _token(client, "claim-admin@test.com", "Admin", "organizer")
    farmer = _token(client, "claim-farmer@test.com", "Farmer", "farmer")
    response = client.post("/onboard", json={
        "farmer_name": "Placeholder",
        "farm_name": "Claimable Farm",
        "pickup_point": "gate",
        "lat": 60.5,
        "lng": 24.7,
    }, headers=_auth(admin))
    assert response.status_code == 201, response.text
    claim_id = response.json()["claim_id"]
    square = client.get("/square").json()
    stall = next(s for s in square["stalls"] if s["farm_name"] == "Claimable Farm")
    assert stall["is_unclaimed"] is True
    assert stall["farmer_name"] == "Unclaimed"
    claimed = client.post("/nodes/claim", json={"claim_id": claim_id}, headers=_auth(farmer))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "pending"
    assert claimed.json()["claimed_at"] is None
    owned = client.get("/nodes", headers=_auth(farmer)).json()
    assert owned == []
    square = client.get("/square").json()
    stall = next(s for s in square["stalls"] if s["farm_name"] == "Claimable Farm")
    assert stall["is_unclaimed"] is True
    assert stall["claim_pending"] is True
    again = client.post("/nodes/claim", json={"claim_id": claim_id}, headers=_auth(farmer))
    assert again.status_code == 200
    assert again.json()["status"] == "pending"
    ok = client.post("/admin/claims", json={"node_id": response.json()["node_id"], "approve": True}, headers=_auth(admin))
    assert ok.status_code == 200
    taken = client.post("/nodes/claim", json={"claim_id": claim_id}, headers=_auth(farmer))
    assert taken.status_code == 409


def test_gate_sale_drops_stock_without_ledger(client):
    org = _token(client, "wade@test.com", "Wade", "organizer")
    start, end = _window()
    farm = client.post("/onboard", json={
        "farmer_name": "Pekka",
        "farm_name": "Backyard",
        "pickup_point": "Bench",
        "lat": 60.63,
        "lng": 24.86,
        "password": "farmgate",
        "email": "pekka@test.com",
        "available_from": start,
        "available_until": end,
        "lots": [{"produce_name": "Peruna", "quantity_kg": 10, "price_per_kg": 0.9}],
    }, headers=_auth(org)).json()
    listing_id = farm["lots"][0]["id"]

    farmer = client.post("/auth/token", data={"username": "pekka@test.com", "password": "farmgate"}).json()["access_token"]
    sold = client.post(f"/listings/{listing_id}/gate", json={"quantity_kg": 3}, headers=_auth(farmer))
    assert sold.status_code == 200, sold.text
    assert sold.json()["remaining_kg"] == 7
    assert sold.json()["settled"] == "cash_at_gate"

    ledger = client.get("/ledger", headers=_auth(org)).json()
    assert not any(row["type"] == "trade" for row in ledger)
    assert any(row["type"] == "farm_onboarding" for row in ledger)

    catalog = client.get("/catalog").json()
    assert catalog["items"][0]["quantity_kg"] == 7
