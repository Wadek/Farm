import pytest


def _register_and_token(client, email="farmer@test.com"):
    client.post("/auth/register", json={
        "email": email, "password": "pass", "name": "Farmer", "role": "farmer"
    })
    resp = client.post("/auth/token", data={"username": email, "password": "pass"})
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_node(client, token):
    resp = client.post("/nodes", json={
        "name": "Test Node", "type": "garden_bed",
        "lat": 60.5522, "lng": 24.7050,
    }, headers=_auth(token))
    return resp.json()["id"]


def _create_produce(client, token, node_id):
    resp = client.post(f"/nodes/{node_id}/produce", json={
        "name": "Tomatoes", "category": "greens",
        "quantity_kg": 10.0, "kcal_per_kg": 180.0, "co2_kg_per_kg": 0.5,
    }, headers=_auth(token))
    assert resp.status_code == 201
    return resp.json()["id"]


# --- Produce ---

def test_add_produce(client):
    token = _register_and_token(client)
    node_id = _create_node(client, token)
    resp = client.post(f"/nodes/{node_id}/produce", json={
        "name": "Carrots", "category": "root",
        "quantity_kg": 5.0, "kcal_per_kg": 410.0, "co2_kg_per_kg": 0.3,
    }, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Carrots"
    assert data["kcal_per_kg"] == 410.0


def test_add_produce_wrong_owner(client):
    token_a = _register_and_token(client, "a@test.com")
    token_b = _register_and_token(client, "b@test.com")
    node_id = _create_node(client, token_a)
    resp = client.post(f"/nodes/{node_id}/produce", json={
        "name": "Tomatoes", "category": "greens",
    }, headers=_auth(token_b))
    assert resp.status_code == 403


def test_list_produce(client):
    token = _register_and_token(client)
    node_id = _create_node(client, token)
    _create_produce(client, token, node_id)
    resp = client.get(f"/nodes/{node_id}/produce")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Tomatoes"


def test_update_produce(client):
    token = _register_and_token(client)
    node_id = _create_node(client, token)
    produce_id = _create_produce(client, token, node_id)
    resp = client.patch(f"/nodes/{node_id}/produce/{produce_id}", json={
        "name": "Tomatoes", "category": "greens",
        "quantity_kg": 25.0, "kcal_per_kg": 180.0, "co2_kg_per_kg": 0.5,
    }, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["quantity_kg"] == 25.0


# --- Listings ---

def test_create_listing(client):
    token = _register_and_token(client)
    node_id = _create_node(client, token)
    produce_id = _create_produce(client, token, node_id)
    resp = client.post(f"/nodes/{node_id}/produce/{produce_id}/listings", json={
        "quantity_kg": 3.0, "price_per_kg": 2.5, "is_free": False,
    }, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["quantity_kg"] == 3.0
    assert data["produce_name"] == "Tomatoes"
    assert data["status"] == "active"


def test_browse_listings_public(client):
    token = _register_and_token(client)
    node_id = _create_node(client, token)
    produce_id = _create_produce(client, token, node_id)
    client.post(f"/nodes/{node_id}/produce/{produce_id}/listings", json={
        "quantity_kg": 2.0, "is_free": True,
    }, headers=_auth(token))
    resp = client.get("/listings")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    item = resp.json()[0]
    assert item["image_url"] == "/static/produce/greens.jpg"
    pic = client.get(item["image_url"])
    assert pic.status_code == 200
    assert pic.headers["content-type"].startswith("image/")


def test_listing_name_picks_a_satokori_woodcut():
    from pathlib import Path
    from app.services.produce_image import produce_image_url
    cases = [
        ("Farm honey", "preserve", "honey.jpg"),
        ("Berry juice", "preserve", "juice.jpg"),
        ("Oat flakes", "preserve", "oats.jpg"),
        ("Organic flour", "preserve", "oats.jpg"),
        ("Alpaca yarn", "preserve", "yarn.jpg"),
        ("Ostrich eggs", "eggs", "ostrich-egg.jpg"),
        ("Raspberries", "berries", "raspberry.jpg"),
        ("blueberries", "berries", "blueberry.jpg"),
        ("Organic strawberries", "berries", "strawberry.jpg"),
        ("Cabbage", "greens", "cabbage.jpg"),
        ("Lehtikaali (kale)", "greens", "greens.jpg"),
        ("Organic vegetables", "greens", "lettuce.jpg"),
        ("Hunaja", "preserve", "honey.jpg"),
        ("Mustikka", "berries", "blueberry.jpg"),
        ("Vadelma", "berries", "raspberry.jpg"),
        ("Mansikka", "berries", "strawberry.jpg"),
        ("Kaura", "preserve", "oats.jpg"),
        ("Strutsin munat", "eggs", "ostrich-egg.jpg"),
        ("Raw milk", "dairy", "dairy.jpg"),
    ]
    pack = Path("static/produce")
    for name, cat, filename in cases:
        assert produce_image_url(name, cat) == f"/static/produce/{filename}", name
        assert (pack / filename).is_file(), filename


def test_stall_upload_gets_named_woodcut(client):
    token = _register_and_token(client, "woodcut-farmer@test.com")
    node_id = _create_node(client, token)
    lots = [
        {"produce_name": "Farm honey", "category": "preserve", "quantity_kg": 1, "price_per_kg": 8, "perpetual": True},
        {"produce_name": "Berry juice", "category": "preserve", "quantity_kg": 1, "price_per_kg": 6, "perpetual": True},
        {"produce_name": "Oat flakes", "category": "preserve", "quantity_kg": 2, "price_per_kg": 4, "perpetual": True},
        {"produce_name": "Alpaca yarn", "category": "preserve", "quantity_kg": 1, "price_per_kg": 30, "perpetual": True},
        {"produce_name": "Ostrich eggs", "category": "eggs", "quantity_kg": 1, "price_per_kg": 12, "perpetual": True},
        {"produce_name": "Raspberries", "category": "berries", "quantity_kg": 1, "price_per_kg": 10, "perpetual": True},
        {"produce_name": "Cabbage", "category": "greens", "quantity_kg": 2, "price_per_kg": 3, "perpetual": True},
    ]
    resp = client.post("/stalls", json={
        "node_id": node_id, "pickup_point": "Farm gate", "lots": lots,
    }, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    want = {
        "Farm honey": "/static/produce/honey.jpg",
        "Berry juice": "/static/produce/juice.jpg",
        "Oat flakes": "/static/produce/oats.jpg",
        "Alpaca yarn": "/static/produce/yarn.jpg",
        "Ostrich eggs": "/static/produce/ostrich-egg.jpg",
        "Raspberries": "/static/produce/raspberry.jpg",
        "Cabbage": "/static/produce/cabbage.jpg",
    }
    for lot in resp.json()["lots"]:
        assert lot["image_url"] == want[lot["produce_name"]], lot
        pic = client.get(lot["image_url"])
        assert pic.status_code == 200, lot["image_url"]
        assert pic.headers["content-type"].startswith("image/")
    catalog = {i["produce_name"]: i["image_url"] for i in client.get("/catalog").json()["items"]}
    for name, src in want.items():
        assert catalog[name] == src


def test_organic_lamb_is_meat_not_feed(client):
    token = _register_and_token(client, "lamb-farmer@test.com")
    node_id = _create_node(client, token)
    resp = client.post("/stalls", json={
        "node_id": node_id,
        "pickup_point": "Farm gate",
        "lots": [{
            "produce_name": "Organic lamb", "category": "feed",
            "quantity_kg": 4, "price_per_kg": 22, "perpetual": True,
        }],
    }, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    lot = resp.json()["lots"][0]
    assert lot["category"] == "meat"
    assert lot["image_url"] == "/static/produce/meat.jpg"
    catalog = client.get("/catalog").json()["items"]
    lamb = next(i for i in catalog if i["produce_name"] == "Organic lamb")
    assert lamb["category"] == "meat"
    assert lamb["image_url"] == "/static/produce/meat.jpg"


def test_browse_listings_with_radius(client):
    token = _register_and_token(client)
    node_id = _create_node(client, token)
    produce_id = _create_produce(client, token, node_id)
    client.post(f"/nodes/{node_id}/produce/{produce_id}/listings", json={
        "quantity_kg": 2.0,
    }, headers=_auth(token))
    # Same coords — within 20km
    resp = client.get("/listings?lat=60.5522&lng=24.7050&radius_km=20")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert "distance_km" in resp.json()[0]

    # Far away — Helsinki city centre ~51km away
    resp2 = client.get("/listings?lat=60.1699&lng=24.9384&radius_km=10")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 0


def test_update_listing_status(client):
    token = _register_and_token(client)
    node_id = _create_node(client, token)
    produce_id = _create_produce(client, token, node_id)
    listing_resp = client.post(f"/nodes/{node_id}/produce/{produce_id}/listings", json={
        "quantity_kg": 1.0,
    }, headers=_auth(token))
    listing_id = listing_resp.json()["id"]
    resp = client.patch(f"/listings/{listing_id}/status?status=reserved", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "reserved"


def test_update_listing_status_wrong_owner(client):
    token_a = _register_and_token(client, "a@test.com")
    token_b = _register_and_token(client, "b@test.com")
    node_id = _create_node(client, token_a)
    produce_id = _create_produce(client, token_a, node_id)
    listing_resp = client.post(f"/nodes/{node_id}/produce/{produce_id}/listings", json={
        "quantity_kg": 1.0,
    }, headers=_auth(token_a))
    listing_id = listing_resp.json()["id"]
    resp = client.patch(f"/listings/{listing_id}/status?status=completed", headers=_auth(token_b))
    assert resp.status_code == 403
