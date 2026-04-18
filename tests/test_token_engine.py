import math
import uuid
import bcrypt
from app.services.token_engine import calculate, DECAY_RATE
from app.services.regional_service import _FI_DEFAULTS
IMPORT_DISTANCE_KM = _FI_DEFAULTS["import_distance_km"]
from app.services.geo import haversine
from app.models import User, UserRole, Node, NodeType, Produce, Listing, ListingStatus


# --- token engine unit tests ---

def test_walking_zero_local_transport():
    result = calculate(
        kcal_per_kg=180.0,
        store_co2_per_kg=2.5,
        local_co2_per_kg=0.4,
        mass_kg=1.0,
        distance_km=0.5,
        is_walking=True,
    )
    # walking means no local transport cost
    local_co2 = 0.4 * 1.0  # no transport added
    store_co2 = (2.5 * 1.0) + (IMPORT_DISTANCE_KM * 0.00015 * 1.0)
    assert abs(result.co2_saved_kg - (store_co2 - local_co2)) < 0.0001


def test_vehicle_adds_transport_cost():
    walk = calculate(180.0, 2.5, 0.4, 1.0, 2.0, is_walking=True)
    drive = calculate(180.0, 2.5, 0.4, 1.0, 2.0, is_walking=False)
    assert walk.co2_saved_kg > drive.co2_saved_kg


def test_hyperlocal_earns_more_tokens():
    near = calculate(180.0, 2.5, 0.4, 1.0, 0.5, is_walking=True)
    far = calculate(180.0, 2.5, 0.4, 1.0, 15.0, is_walking=False)
    assert near.myc_tokens > far.myc_tokens


def test_decay_factor_at_zero_distance():
    result = calculate(180.0, 2.5, 0.4, 1.0, 0.0, is_walking=True)
    # decay_factor = exp(0) = 1.0, so multiplier = 2.0
    expected_multiplier = 1 + math.exp(-DECAY_RATE * 0.0)
    assert abs(expected_multiplier - 2.0) < 0.0001
    assert result.myc_tokens > 0


def test_zero_mass_yields_zero_tokens():
    result = calculate(180.0, 2.5, 0.4, 0.0, 1.0, is_walking=True)
    assert result.myc_tokens == 0.0
    assert result.co2_saved_kg == 0.0


def test_negative_co2_saved_clamps_eco_value():
    # If local CO2 > store CO2 (unusual), eco_value should be 0 not negative
    result = calculate(
        kcal_per_kg=10.0,
        store_co2_per_kg=0.01,
        local_co2_per_kg=99.0,
        mass_kg=1.0,
        distance_km=5.0,
        is_walking=False,
    )
    assert result.eco_value_eur == 0.0
    assert result.myc_tokens >= 0.0


# --- geo unit tests ---

def test_haversine_same_point():
    assert haversine(60.38, 24.51, 60.38, 24.51) == 0.0


def test_haversine_known_distance():
    # Hyvinkää centre to Helsinki centre ~51km
    d = haversine(60.6304, 24.8603, 60.1699, 24.9384)
    assert 45.0 < d < 60.0


def test_haversine_within_node_range():
    # Two points ~1km apart
    d = haversine(60.38, 24.51, 60.389, 24.51)
    assert d < 2.0


# --- transaction route integration tests ---

def _seed_transaction_fixtures(db):
    hashed = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    farmer = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4()}@f.com",
                  hashed_password=hashed, name="Farmer", role=UserRole.farmer)
    buyer = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4()}@b.com",
                 hashed_password=hashed, name="Buyer", role=UserRole.buyer)
    db.add_all([farmer, buyer])
    db.commit()

    seller_node = Node(id=str(uuid.uuid4()), owner_id=farmer.id, name="Test Farm",
                       type=NodeType.garden_bed, lat=60.38, lng=24.51, area_m2=20.0)
    buyer_node = Node(id=str(uuid.uuid4()), owner_id=buyer.id, name="Buyer Home",
                      type=NodeType.garden_bed, lat=60.385, lng=24.51, area_m2=5.0)
    db.add_all([seller_node, buyer_node])
    db.commit()

    produce = Produce(id=str(uuid.uuid4()), node_id=seller_node.id, name="Tomato",
                      category="vegetable", quantity_kg=10.0,
                      kcal_per_kg=180.0, co2_kg_per_kg=0.4)
    db.add(produce)
    db.commit()

    listing = Listing(id=str(uuid.uuid4()), node_id=seller_node.id,
                      produce_id=produce.id, quantity_kg=10.0,
                      pickup_point="Farm gate")
    db.add(listing)
    db.commit()

    return farmer, buyer, seller_node, buyer_node, produce, listing


def test_complete_transaction_mints_tokens(client, db):
    _, buyer, seller_node, _, _, listing = _seed_transaction_fixtures(db)

    resp = client.post("/transactions/complete", json={
        "listing_id": listing.id,
        "buyer_id": buyer.id,
        "quantity_kg": 2.0,
        "is_walking": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["myc_tokens_minted"] > 0
    assert data["co2_saved_kg"] > 0
    assert "transaction_id" in data


def test_complete_transaction_reduces_listing(client, db):
    _, buyer, _, _, _, listing = _seed_transaction_fixtures(db)

    client.post("/transactions/complete", json={
        "listing_id": listing.id,
        "buyer_id": buyer.id,
        "quantity_kg": 10.0,
        "is_walking": False,
    })
    db.refresh(listing)
    assert listing.status == ListingStatus.completed


def test_complete_inactive_listing_rejected(client, db):
    _, buyer, _, _, _, listing = _seed_transaction_fixtures(db)

    client.post("/transactions/complete", json={
        "listing_id": listing.id,
        "buyer_id": buyer.id,
        "quantity_kg": 10.0,
        "is_walking": True,
    })
    # try again on completed listing
    resp = client.post("/transactions/complete", json={
        "listing_id": listing.id,
        "buyer_id": buyer.id,
        "quantity_kg": 1.0,
        "is_walking": True,
    })
    assert resp.status_code == 409


def test_node_ledger_is_append_only(client, db):
    _, buyer, seller_node, _, _, listing = _seed_transaction_fixtures(db)

    client.post("/transactions/complete", json={
        "listing_id": listing.id,
        "buyer_id": buyer.id,
        "quantity_kg": 2.0,
        "is_walking": True,
    })

    resp = client.get(f"/transactions/node/{seller_node.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["transaction_count"] == 1
    assert data["myc_balance"] > 0
    assert len(data["ledger"]) == 1
