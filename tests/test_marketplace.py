from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    start = datetime.now().replace(microsecond=0) + timedelta(days=2, hours=2)
    end = start + timedelta(minutes=30)
    return start.isoformat(), end.isoformat()


def test_featured_stays_on_reko_filter_in_the_page():
    html = (ROOT / "static" / "square.html").read_text(encoding="utf-8")
    assert "if (item.featured) return true;" in html
    assert "function isLiveFarm" in html
    assert 't("Live")' in html
    assert "radius_km=80" in html
    assert "tile-flag live" in html


def test_siuntio_ring_and_farms_are_in_seed():
    seed = (ROOT / "seed.py").read_text(encoding="utf-8")
    assert "REKO Siuntio" in seed
    assert "Åke Tottin" in seed
    assert "Tuiskula Farm" in seed
    assert "IS-Farmi" in seed
    assert "ring-siuntio" in seed
    assert "Haskap (hunajamarja)" in seed
    assert "def ensure" in seed


def test_claimed_farm_listing_is_live_not_demo_tag(client):
    token, _ = _register(client, "live-farm@test.com", "Niina", "farmer")
    node = client.post("/nodes", json={
        "name": "Toikantila", "type": "farm", "lat": 60.50, "lng": 24.76,
    }, headers=_auth(token)).json()
    stall = client.post("/stalls", json={
        "node_id": node["id"], "pickup_point": "Farm gate",
        "lots": [{"produce_name": "Raw milk", "category": "dairy", "quantity_kg": 8,
                  "price_per_kg": 1.4, "unit": "L", "perpetual": True}],
    }, headers=_auth(token))
    assert stall.status_code == 201, stall.text
    lot = stall.json()["lots"][0]
    assert lot["claimed"] is True
    assert lot["demo"] is False
    catalog = client.get("/catalog").json()["items"]
    milk = next(i for i in catalog if i["produce_name"] == "Raw milk")
    assert milk["claimed"] is True
    assert milk["farmer_id"]
    html = client.get("/").text
    assert "isLiveFarm" in html
    assert 't("Live")' in html


def test_unclaimed_farm_is_not_live(client):
    admin, _ = _register(client, "demo-admin@test.com", "Admin", "organizer")
    start, end = _window()
    farm = client.post("/onboard", json={
        "farmer_name": "Placeholder",
        "farm_name": "Open Dairy",
        "pickup_point": "gate",
        "lat": 60.5, "lng": 24.7,
        "available_from": start,
        "available_until": end,
        "lots": [{"produce_name": "Milk", "category": "dairy", "quantity_kg": 4,
                  "price_per_kg": 1.4, "unit": "L", "demo": True}],
    }, headers=_auth(admin))
    assert farm.status_code == 201, farm.text
    catalog = client.get("/catalog").json()["items"]
    milk = next(i for i in catalog if i["farm_name"] == "Open Dairy")
    assert milk["claimed"] is False
    assert not milk["farmer_id"]


def test_reko_drop_nearby_includes_far_farm(client):
    admin, _ = _register(client, "dist-admin@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "dist-farmer@test.com", "Essi", "farmer")
    start, end = _window()
    drop = client.post("/rings", json={
        "name": "REKO Siuntio",
        "place": "Åke Tottin tien pysäköintialue",
        "lat": 60.5522, "lng": 24.7050,
        "starts_at": start, "ends_at": end,
    }, headers=_auth(admin)).json()
    node = client.post("/nodes", json={
        "name": "Tuiskula Farm", "type": "farm",
        "lat": 60.1750, "lng": 24.1480,
    }, headers=_auth(farmer)).json()
    listing = client.post("/stalls", json={
        "node_id": node["id"], "drop_id": drop["id"], "pickup_point": "lot",
        "lots": [{"produce_name": "Pasture eggs", "category": "eggs", "quantity_kg": 12,
                  "price_per_kg": 0.45, "unit": "kpl"}],
    }, headers=_auth(farmer))
    assert listing.status_code == 201, listing.text
    near = client.get("/catalog?lat=60.5522&lng=24.7050&radius_km=20").json()["items"]
    names = [i["produce_name"] for i in near]
    assert "Pasture eggs" in names
    far_only = client.get("/catalog?lat=60.5522&lng=24.7050&radius_km=5").json()["items"]
    assert any(i["produce_name"] == "Pasture eggs" for i in far_only)


def test_featured_farm_gate_is_first_in_catalog(client, db):
    admin, _ = _register(client, "feat-reko@test.com", "Admin", "organizer")
    farmer, _ = _register(client, "feat-reko-farm@test.com", "Niina", "farmer")
    start, end = _window()
    drop = client.post("/rings", json={
        "name": "REKO Nurmijärvi", "place": "kirkonkylä",
        "lat": 60.46, "lng": 24.80, "starts_at": start, "ends_at": end,
    }, headers=_auth(admin)).json()
    node = client.post("/nodes", json={
        "name": "Feat Farm", "type": "farm", "lat": 60.55, "lng": 24.70,
    }, headers=_auth(farmer)).json()
    gate = client.post("/stalls", json={
        "node_id": node["id"], "pickup_point": "gate",
        "lots": [{"produce_name": "Hay", "category": "feed", "quantity_kg": 10,
                  "price_per_kg": 0.2, "perpetual": True}],
    }, headers=_auth(farmer)).json()["lots"][0]
    client.post("/stalls", json={
        "node_id": node["id"], "drop_id": drop["id"], "pickup_point": "lot",
        "lots": [{"produce_name": "Milk", "category": "dairy", "quantity_kg": 4,
                  "price_per_kg": 1.4, "unit": "L"}],
    }, headers=_auth(farmer))
    client.post("/admin/featured", json={"listing_id": gate["id"]}, headers=_auth(admin))
    catalog = client.get("/catalog").json()["items"]
    assert catalog[0]["produce_name"] == "Hay"
    assert catalog[0]["featured"] is True
    assert catalog[0]["drop"] is None
    html = client.get("/").text
    assert "if (item.featured) return true;" in html
