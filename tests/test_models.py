import uuid
import bcrypt
from app.models import User, UserRole, Node, NodeType, Produce, Listing, ListingStatus, Transaction, Message


def make_user(role=UserRole.farmer):
    hashed = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    return User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@test.com",
        hashed_password=hashed,
        name="Test User",
        role=role,
    )


def make_node(owner_id):
    return Node(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name="Test Garden",
        type=NodeType.garden_bed,
        lat=60.3,
        lng=24.9,
        area_m2=10.0,
    )


def make_produce(node_id):
    return Produce(
        id=str(uuid.uuid4()),
        node_id=node_id,
        name="Tomato",
        category="vegetable",
        quantity_kg=5.0,
        kcal_per_kg=180.0,
        co2_kg_per_kg=0.4,
    )


def test_create_user(db):
    user = make_user()
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.id is not None
    assert user.role == UserRole.farmer


def test_create_node(db):
    user = make_user()
    db.add(user)
    db.commit()

    node = make_node(user.id)
    db.add(node)
    db.commit()
    db.refresh(node)
    assert node.owner_id == user.id
    assert node.myc_tokens == 0.0


def test_create_produce(db):
    user = make_user()
    db.add(user)
    db.commit()

    node = make_node(user.id)
    db.add(node)
    db.commit()

    produce = make_produce(node.id)
    db.add(produce)
    db.commit()
    db.refresh(produce)
    assert produce.name == "Tomato"
    assert produce.kcal_per_kg == 180.0


def test_create_listing(db):
    user = make_user()
    db.add(user)
    db.commit()

    node = make_node(user.id)
    db.add(node)
    db.commit()

    produce = make_produce(node.id)
    db.add(produce)
    db.commit()

    listing = Listing(
        id=str(uuid.uuid4()),
        node_id=node.id,
        produce_id=produce.id,
        quantity_kg=2.0,
        pickup_point="Farm gate",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    assert listing.status == ListingStatus.active


def test_create_transaction(db):
    farmer = make_user(UserRole.farmer)
    buyer = make_user(UserRole.buyer)
    db.add_all([farmer, buyer])
    db.commit()

    node = make_node(farmer.id)
    db.add(node)
    db.commit()

    produce = make_produce(node.id)
    db.add(produce)
    db.commit()

    listing = Listing(
        id=str(uuid.uuid4()),
        node_id=node.id,
        produce_id=produce.id,
        quantity_kg=2.0,
        pickup_point="Farm gate",
    )
    db.add(listing)
    db.commit()

    tx = Transaction(
        id=str(uuid.uuid4()),
        listing_id=listing.id,
        buyer_id=buyer.id,
        quantity_kg=1.0,
        distance_km=1.5,
        co2_saved_kg=0.8,
        myc_tokens_minted=12.4,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    assert tx.myc_tokens_minted == 12.4


def test_create_message(db):
    farmer = make_user(UserRole.farmer)
    buyer = make_user(UserRole.buyer)
    db.add_all([farmer, buyer])
    db.commit()

    msg = Message(
        id=str(uuid.uuid4()),
        sender_id=buyer.id,
        recipient_id=farmer.id,
        body="Is the tomato still available?",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    assert msg.read is False


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
