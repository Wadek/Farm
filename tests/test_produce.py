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
        "name": "Tomatoes", "category": "vegetable",
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
        "name": "Tomatoes", "category": "vegetable",
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
        "name": "Tomatoes", "category": "vegetable",
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
