"""Seed a local Hyvinkää market square for trying Perinnepelto."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import (
    DemandFlare,
    Listing,
    ListingStatus,
    Node,
    NodeType,
    Produce,
    User,
    UserRole,
)
from app.models.flare import FlareStatus
from app.services.auth_service import hash_password

from app.config import settings

DATA_DIR = Path("data")


def _saturday_window():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_ahead = (5 - today.weekday()) % 7
    if days_ahead == 0 and datetime.now().hour >= 14:
        days_ahead = 7
    saturday = today + timedelta(days=days_ahead)
    return saturday.replace(hour=10), saturday.replace(hour=14)


def _user(db: Session, user_id: str, email: str, password: str, name: str, role: UserRole,
          phone: str = "") -> User:
    user = User(
        id=user_id,
        email=email,
        hashed_password=hash_password(password),
        name=name,
        role=role,
        phone=phone,
    )
    db.add(user)
    return user


def _node(db: Session, node_id: str, owner_id: str, name: str, ntype: NodeType,
          lat: float, lng: float, description: str, area_m2: float,
          claim_id: str | None = None, claimed_at: datetime | None = None) -> Node:
    node = Node(
        id=node_id,
        owner_id=owner_id,
        name=name,
        type=ntype,
        lat=lat,
        lng=lng,
        description=description,
        area_m2=area_m2,
        myc_tokens=0.0,
        claim_id=claim_id or f"claim-{node_id}",
        claimed_at=claimed_at,
    )
    db.add(node)
    return node


def _lot(db: Session, listing_id: str, node_id: str, produce_id: str, name: str,
         category: str, qty: float, price: float, kcal: float, co2: float,
         pickup: str, available_from: datetime, available_until: datetime,
         is_free: bool = False, unit: str = "kg"):
    produce = Produce(
        id=produce_id,
        node_id=node_id,
        name=name,
        category=category,
        quantity_kg=qty,
        kcal_per_kg=kcal,
        co2_kg_per_kg=co2,
    )
    db.add(produce)
    listing = Listing(
        id=listing_id,
        node_id=node_id,
        produce_id=produce_id,
        quantity_kg=qty,
        unit=unit,
        price_per_kg=price,
        pickup_point=pickup,
        is_free=is_free or price == 0,
        available_from=available_from,
        available_until=available_until,
        status=ListingStatus.active,
    )
    db.add(listing)


def seed():
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        raw = db_url.replace("sqlite:///", "", 1)
        Path(raw).parent.mkdir(parents=True, exist_ok=True)
    else:
        DATA_DIR.mkdir(exist_ok=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    opens, closes = _saturday_window()
    db = SessionLocal()
    try:
        wade = _user(db, "user-wade", "wade@kariniemi.farm", "farmgate", "Wade Kariniemi",
                     UserRole.organizer, phone="+358403333333")
        maija = _user(db, "user-maija", "maija@naapuri.fi", "farmgate", "Maija Niemi",
                      UserRole.farmer, phone="+358401111111")
        pekka = _user(db, "user-pekka", "pekka@hyvinkaa.fi", "farmgate", "Pekka Laine",
                      UserRole.farmer, phone="+358404444444")
        anna = _user(db, "user-anna", "anna@hyvinkaa.fi", "market", "Anna Virtanen",
                     UserRole.buyer, phone="+358402222222")
        liisa = _user(db, "user-liisa", "liisa@hyvinkaa.fi", "market", "Liisa Customer",
                  UserRole.buyer, phone="+358405555555")

        claimed_now = datetime.now(timezone.utc)
        kariniemi = _node(
            db, "node-kariniemi", wade.id, "Kariniemi Farms", NodeType.farm,
            60.5522, 24.7050,
            "Korpiharjuntie, Yli-Solttila — farm gate, look for the painted sign.",
            50000,
            claim_id="claim-kariniemi",
            claimed_at=claimed_now,
        )
        rajamaki = _node(
            db, "node-rajamaki", maija.id, "Rajamäki Heritage Beds", NodeType.hobby_farm,
            60.5270, 24.7500,
            "Raised beds behind the red shed. Knock if the kettle is on.",
            800,
            claim_id="claim-rajamaki",
            claimed_at=claimed_now,
        )
        backyard = _node(
            db, "node-hyvinkaa", pekka.id, "Pekka's Backyard", NodeType.backyard,
            60.6304, 24.8603,
            "Hyvinkää yard gate on Saturday — crate on the bench if we're in the sauna.",
            120,
            claim_id="claim-backyard",
            claimed_at=claimed_now,
        )
        kumpula = _node(
            db, "node-kumpula", None, "Kumpula Apple Orchard", NodeType.farm,
            60.5100, 24.7800,
            "Kumpulantie 12, Hyvinkää — orchard gate.",
            15000,
            claim_id="claim-kumpula-2026",
            claimed_at=None,
        )
        db.flush()

        _lot(db, "lot-kale", kariniemi.id, "prod-kale", "Lehtikaali (kale)", "greens",
             8.0, 4.0, 490, 0.4, kariniemi.description, opens, closes, unit="kg")
        _lot(db, "lot-eggs", kariniemi.id, "prod-eggs", "Farm eggs", "eggs",
             30.0, 0.40, 1430, 2.1, kariniemi.description, opens, closes, unit="kpl")
        _lot(db, "lot-hay", kariniemi.id, "prod-hay", "Small-square hay", "feed",
             40.0, 0.25, 0, 0.05, kariniemi.description, opens, closes, unit="kg")

        _lot(db, "lot-honey", rajamaki.id, "prod-honey", "Village honey", "preserve",
             12.0, 8.0, 3040, 0.3, rajamaki.description, opens, closes, unit="kpl")
        _lot(db, "lot-carrot", rajamaki.id, "prod-carrot", "Porkkana", "root",
             12.0, 1.8, 410, 0.3, rajamaki.description, opens, closes, unit="kg")
        _lot(db, "lot-milk", rajamaki.id, "prod-milk", "Raw milk", "dairy",
             20.0, 1.4, 640, 1.2, rajamaki.description, opens, closes, unit="L")
        _lot(db, "lot-berries", rajamaki.id, "prod-berries", "Mustikka", "berries",
             8.0, 12.0, 570, 0.2, rajamaki.description, opens, closes, unit="L")

        _lot(db, "lot-potato", backyard.id, "prod-potato", "Peruna", "root",
             25.0, 0.9, 770, 0.2, backyard.description, opens, closes, unit="kg")
        _lot(db, "lot-surplus", backyard.id, "prod-surplus", "Surplus courgettes", "vegetable",
             4.0, 0.0, 170, 0.3, backyard.description, opens, closes, is_free=True, unit="kg")

        _lot(db, "lot-apples", kumpula.id, "prod-apples", "Summer apples (omena)", "berries",
             20.0, 2.5, 520, 0.2, kumpula.description, opens, closes, unit="kg")

        db.add(DemandFlare(
            id="flare-milk",
            buyer_id=anna.id,
            item="Raw milk",
            quantity_note="5 litres this Saturday",
            radius_km=20.0,
            lat=60.6304,
            lng=24.8603,
            status=FlareStatus.open,
        ))

        db.commit()
        print("Seeded Satokori")
        print(f"  Pickup window: {opens:%a %d %b %H:%M} – {closes:%H:%M}")
        print()
        print("Organizer (password: farmgate)  — field visits")
        print("  wade@kariniemi.farm   Kariniemi Farms")
        print("Farmers   (password: farmgate)")
        print("  maija@naapuri.fi      Rajamäki Heritage Beds")
        print("  pekka@hyvinkaa.fi     Pekka's Backyard")
        print("Unclaimed Farm (claim ID: claim-kumpula-2026)")
        print("  Kumpula Apple Orchard")
        print("Customer  (password: market)")
        print("  anna@hyvinkaa.fi      looking for raw milk")
        print("  liisa@hyvinkaa.fi     second customer test account")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
