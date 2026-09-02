"""Seed Kariniemi + nearby farms. Dummy lots are marked demo."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Listing, ListingStatus, Node, NodeType, Produce, Ring, RingDrop, User, UserRole
from app.services.auth_service import hash_password

DATA_DIR = Path("data")


def _user(db: Session, user_id: str, email: str, password: str, name: str, role: UserRole,
          phone: str = "") -> User:
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
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


def _node(db: Session, node_id: str, owner_id: str | None, name: str, ntype: NodeType,
          lat: float, lng: float, description: str, area_m2: float,
          claim_id: str | None = None, claimed_at: datetime | None = None,
          created_at: datetime | None = None) -> Node:
    existing = db.query(Node).filter(Node.id == node_id).first()
    if existing:
        return existing
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
        created_at=created_at,
    )
    db.add(node)
    return node


def _lot(db: Session, listing_id: str, node_id: str, produce_id: str, name: str,
         category: str, qty: float, price: float, kcal: float, co2: float,
         pickup: str, unit: str = "kg", perpetual: bool = False,
         demo: bool = True, featured: bool = False, drop_id: str | None = None,
         available_from=None, available_until=None):
    existing = db.query(Listing).filter(Listing.id == listing_id).first()
    if existing:
        return existing
    produce = db.query(Produce).filter(Produce.id == produce_id).first()
    if produce is None:
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
        is_free=price == 0,
        available_from=available_from,
        available_until=available_until,
        perpetual=perpetual and not drop_id,
        demo=demo,
        featured=featured,
        drop_id=drop_id,
        status=ListingStatus.active,
    )
    db.add(listing)
    return listing


def seed(reset: bool = True):
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        raw = db_url.replace("sqlite:///", "", 1)
        Path(raw).parent.mkdir(parents=True, exist_ok=True)
    else:
        DATA_DIR.mkdir(exist_ok=True)
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        wade = _user(
            db, "user-wade", "wkariniemi@proton.me", "farmgate", "Wade Kariniemi",
            UserRole.organizer, phone="0453549844",
        )

        # Oldest first so Toikantila (today's visit) is the latest farm at the top.
        t0 = now - timedelta(days=10)
        kariniemi = _node(
            db, "node-kariniemi", wade.id, "Kariniemi Farms", NodeType.farm,
            60.5522, 24.7050,
            "Korpiharjuntie 363, 05200 Rajamäki.",
            50000,
            claim_id="claim-kariniemi",
            claimed_at=now,
            created_at=t0,
        )
        farms = [
            ("node-ketola", "Ketolan strutsitila", NodeType.farm,
             60.5305, 24.7488,
             "Korvenojantie 17, 05200 Rajamäki — ostrich meat and eggs. Instagram @strutsitarhaketolantila.",
             8000, t0 + timedelta(days=1)),
            ("node-mattila", "Mattilan luomumansikka", NodeType.hobby_farm,
             60.5152, 24.7684,
             "Uudenkylänpolku 1, Rajamäki — organic strawberry and tomato. 040 582 7497.",
             4000, t0 + timedelta(days=2)),
            ("node-wennborg", "Wennborgin Tila", NodeType.farm,
             60.5904, 24.6518,
             "Suopellontie 320, 05720 Hyvinkää (Kytäjä) — berries, vegetables, juices. Shop 8–20. 045 330 8899.",
             12000, t0 + timedelta(days=3)),
            ("node-myllymaa", "Myllymaan marjatila", NodeType.hobby_farm,
             60.4896, 24.7892,
             "Myllykoski, Nurmijärvi — raspberry, honey, eggs. Call first: 050 2660.",
             3000, t0 + timedelta(days=4)),
            ("node-vaihia", "Vaihian tila", NodeType.farm,
             60.4548, 24.7210,
             "Haimoontie 31, 05100 Nurmijärvi — cabbage, seasonal kiosk. 040 751 9318.",
             6000, t0 + timedelta(days=5)),
            ("node-kranni", "Krannin tila", NodeType.farm,
             60.4082, 24.6554,
             "Takkulantie 9, 01830 Lepsämä — mill flour, flakes, bran. Shop Fri 15–18, Sat 12–16. 050 300 0756.",
             15000, t0 + timedelta(days=6)),
            ("node-knehtila", "Knehtilän tila", NodeType.farm,
             60.5964, 24.9270,
             "Haapasaarentie 75, 05470 Palopuro — organic grain, café and shop. 040 048 9350.",
             20000, t0 + timedelta(days=7)),
            ("node-mantymaeki", "Mäntymäen Luomutila", NodeType.farm,
             60.5764, 24.9372,
             "Mäntymäentie 52, Palopuro — organic eggs. Shop Sat 10–13. 050 345 0703.",
             5000, t0 + timedelta(days=8)),
            ("node-ylisjoki", "Ylisjoen tila", NodeType.farm,
             60.3824, 24.7518,
             "Gunnarintie 11, 01800 Klaukkala — tinkimaito, pickup 17:00–17:30. 040 093 7427.",
             18000, t0 + timedelta(days=9)),
            ("node-toikantila", "Toikantila", NodeType.farm,
             60.5084, 24.7616,
             "Pirttimäentie 178, 05200 Rajamäki — milk, meat, hay. Niina Toikka 044 210 4990.",
             40000, now),
            ("node-airikkala", "Airikkalan luomutila", NodeType.farm,
             60.4302, 24.7058,
             "Airikkalantie 48, 01860 Perttula — Finnish sheep, cut flowers, lamb. Mona and Ilari Airikkala.",
             8000, now - timedelta(hours=8)),
            ("node-lohenoja", "Lohenojan luomutila", NodeType.farm,
             60.4484, 24.6886,
             "Nummenpää, Klaukkala — organic vegetables. Sells through Nurmijärvi and Hyvinkää REKO.",
             6000, now - timedelta(hours=6)),
            ("node-aliolli", "Aliollin alpakkatila", NodeType.hobby_farm,
             60.3752, 24.7184,
             "Kuonomäentie 117, 01800 Klaukkala — alpaca wool and farm visits.",
             4000, now - timedelta(hours=4)),
            ("node-tuiskula", "Tuiskula Farm", NodeType.farm,
             60.1750, 24.1480,
             "Lappersintie 496, 02590 Siuntio — pasture eggs and vegetables. tuiskulafarm.com. Sells through REKO.",
             8000, now - timedelta(hours=2)),
            ("node-isfarmi", "IS-Farmi", NodeType.farm,
             60.1420, 24.2070,
             "Suitiantie 251, 02570 Siuntio — haskap and sea buckthorn. maatilasiuntiossa.fi.",
             5000, now - timedelta(hours=1)),
        ]
        nodes = {"node-kariniemi": kariniemi}
        for node_id, name, ntype, lat, lng, desc, area, created in farms:
            nodes[node_id] = _node(
                db, node_id, None, name, ntype, lat, lng, desc, area,
                claim_id=f"claim-{node_id.replace('node-', '')}",
                claimed_at=None,
                created_at=created,
            )
        db.flush()

        def _next_weekday(weekday: int, hour: int, minute: int):
            d = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            days = (weekday - d.weekday()) % 7
            if days == 0 and d <= now:
                days = 7
            return d + timedelta(days=days)

        hy_start = _next_weekday(2, 18, 0)
        hy_end = hy_start + timedelta(minutes=30)
        nj_start = _next_weekday(3, 17, 30)
        nj_end = nj_start + timedelta(minutes=30)

        def _upsert_ring(ring_id, name, place, lat, lng, notes, facebook_url, claim_id):
            row = db.query(Ring).filter(Ring.id == ring_id).first()
            if row:
                row.place = place
                row.notes = notes
                row.facebook_url = facebook_url
                return row
            row = Ring(
                id=ring_id, name=name, place=place, lat=lat, lng=lng,
                notes=notes, facebook_url=facebook_url, claim_id=claim_id,
            )
            db.add(row)
            return row

        def _upsert_drop(drop_id, ring_id, starts, ends):
            row = db.query(RingDrop).filter(RingDrop.id == drop_id).first()
            if row:
                row.starts_at = starts
                row.ends_at = ends
                row.order_until = starts - timedelta(hours=6)
                return row
            row = RingDrop(
                id=drop_id, ring_id=ring_id,
                starts_at=starts, ends_at=ends,
                order_until=starts - timedelta(hours=6),
            )
            db.add(row)
            return row

        hyvinkaa = _upsert_ring(
            "ring-hyvinkaa",
            "Hyvinkään Farmarin Markkinat / REKO",
            "Mäkikuumolantie 3, Hyvinkää",
            60.6325, 24.8635,
            "Every other Wednesday 18:00–18:30. Order a quantity on the listing. Cash or MobilePay at the lot. No middleman.",
            "https://www.facebook.com/groups/hyvinkaanreko",
            "claim-ring-hyvinkaa",
        )
        nurmijarvi = _upsert_ring(
            "ring-nurmijarvi",
            "REKO Nurmijärvi",
            "Nurmijärven kirkonkylä (confirm lot in the Facebook group)",
            60.4641, 24.8072,
            "Order a quantity. Cash or MobilePay at the lot. Ring admin sets the exact lot.",
            "https://www.facebook.com/groups/rekonurmijarvi",
            "claim-ring-nurmijarvi",
        )
        si_start = _next_weekday(3, 20, 0)
        # Odd ISO week Thursday 20:00–20:15.
        while si_start.isocalendar()[1] % 2 == 0:
            si_start += timedelta(days=7)
        si_end = si_start + timedelta(minutes=15)
        siuntio = _upsert_ring(
            "ring-siuntio",
            "REKO Siuntio",
            "Åke Tottin tien pysäköintialue, Flemingintie–Ratapihantie, Siuntio",
            60.1409, 24.2223,
            "Odd-week Thursday 20:00–20:15. Order a quantity on the listing. Cash or MobilePay at the lot.",
            "https://www.facebook.com/groups/434382883432989",
            "claim-ring-siuntio",
        )
        db.flush()
        drop_hy = _upsert_drop("drop-hyvinkaa-next", hyvinkaa.id, hy_start, hy_end)
        drop_nj = _upsert_drop("drop-nurmijarvi-next", nurmijarvi.id, nj_start, nj_end)
        drop_si = _upsert_drop("drop-siuntio-next", siuntio.id, si_start, si_end)
        db.flush()

        _lot(db, "lot-kale", kariniemi.id, "prod-kale", "Lehtikaali (kale)", "greens",
             8.0, 4.0, 490, 0.4, kariniemi.description, unit="kg", perpetual=False)
        _lot(db, "lot-eggs", kariniemi.id, "prod-eggs", "Farm eggs", "eggs",
             30.0, 0.40, 1430, 2.1, kariniemi.description, unit="kpl", perpetual=True)
        _lot(db, "lot-hay-k", kariniemi.id, "prod-hay-k", "Small-square hay", "feed",
             40.0, 0.25, 0, 0.05, kariniemi.description, unit="kg", perpetual=True)

        toika = nodes["node-toikantila"]
        _lot(db, "lot-milk-toikka", toika.id, "prod-milk-toikka", "Raw milk", "dairy",
             20.0, 1.4, 640, 1.2, toika.description, unit="L", perpetual=True)
        _lot(db, "lot-beef", toika.id, "prod-beef", "Farm beef", "meat",
             10.0, 18.0, 2500, 12.0, toika.description, unit="kg", perpetual=True)
        _lot(db, "lot-hay-t", toika.id, "prod-hay-t", "Hay bales", "feed",
             50.0, 0.20, 0, 0.05, toika.description, unit="kg", perpetual=True)

        _lot(db, "lot-ostrich", nodes["node-ketola"].id, "prod-ostrich", "Ostrich eggs", "eggs",
             6.0, 8.0, 1400, 2.0, nodes["node-ketola"].description, unit="kpl", perpetual=True)
        _lot(db, "lot-strawberry-m", nodes["node-mattila"].id, "prod-strawberry-m", "Organic strawberries",
             "berries", 12.0, 10.0, 320, 0.3, nodes["node-mattila"].description, unit="kg")
        _lot(db, "lot-berry-w", nodes["node-wennborg"].id, "prod-berry-w", "Farm strawberries",
             "berries", 15.0, 9.0, 320, 0.3, nodes["node-wennborg"].description, unit="kg")
        _lot(db, "lot-juice", nodes["node-wennborg"].id, "prod-juice", "Berry juice",
             "preserve", 20.0, 6.0, 180, 0.2, nodes["node-wennborg"].description, unit="L", perpetual=True)
        _lot(db, "lot-raspberry", nodes["node-myllymaa"].id, "prod-raspberry", "Raspberries",
             "berries", 8.0, 12.0, 520, 0.2, nodes["node-myllymaa"].description, unit="kg")
        _lot(db, "lot-honey", nodes["node-myllymaa"].id, "prod-honey", "Farm honey",
             "preserve", 10.0, 8.0, 3040, 0.3, nodes["node-myllymaa"].description, unit="kpl", perpetual=True)
        _lot(db, "lot-cabbage", nodes["node-vaihia"].id, "prod-cabbage", "Cabbage",
             "greens", 30.0, 1.2, 250, 0.2, nodes["node-vaihia"].description, unit="kg")
        _lot(db, "lot-flakes", nodes["node-kranni"].id, "prod-flakes", "Oat flakes",
             "preserve", 25.0, 3.5, 3700, 0.4, nodes["node-kranni"].description, unit="kg", perpetual=True)
        _lot(db, "lot-flour", nodes["node-knehtila"].id, "prod-flour", "Organic flour",
             "preserve", 20.0, 2.8, 3600, 0.4, nodes["node-knehtila"].description, unit="kg", perpetual=True)
        _lot(db, "lot-eggs-m", nodes["node-mantymaeki"].id, "prod-eggs-m", "Organic eggs",
             "eggs", 60.0, 0.50, 1430, 1.8, nodes["node-mantymaeki"].description, unit="kpl", perpetual=True)
        _lot(db, "lot-milk-y", nodes["node-ylisjoki"].id, "prod-milk-y", "Tinkimaito",
             "dairy", 15.0, 1.5, 640, 1.2, nodes["node-ylisjoki"].description, unit="L", perpetual=True)

        _lot(db, "lot-lamb-a", nodes["node-airikkala"].id, "prod-lamb-a", "Organic lamb",
             "meat", 6.0, 22.0, 2400, 10.0, nodes["node-airikkala"].description, unit="kg", perpetual=True)
        _lot(db, "lot-veg-l", nodes["node-lohenoja"].id, "prod-veg-l", "Organic vegetables",
             "greens", 20.0, 3.5, 250, 0.2, nodes["node-lohenoja"].description, unit="kg")
        _lot(db, "lot-wool-a", nodes["node-aliolli"].id, "prod-wool-a", "Alpaca yarn",
             "preserve", 8.0, 18.0, 0, 0.1, nodes["node-aliolli"].description, unit="kpl", perpetual=True)
        _lot(db, "lot-eggs-tuiskula", nodes["node-tuiskula"].id, "prod-eggs-tuiskula", "Pasture eggs",
             "eggs", 40.0, 0.45, 1430, 1.6, nodes["node-tuiskula"].description, unit="kpl", perpetual=True)
        _lot(db, "lot-veg-tuiskula", nodes["node-tuiskula"].id, "prod-veg-tuiskula", "Farm vegetables",
             "greens", 12.0, 3.5, 250, 0.2, nodes["node-tuiskula"].description, unit="kg")
        _lot(db, "lot-haskap", nodes["node-isfarmi"].id, "prod-haskap", "Haskap (hunajamarja)",
             "berries", 8.0, 14.0, 470, 0.3, nodes["node-isfarmi"].description, unit="kg")
        _lot(db, "lot-tyrni", nodes["node-isfarmi"].id, "prod-tyrni", "Tyrni",
             "berries", 6.0, 16.0, 820, 0.3, nodes["node-isfarmi"].description, unit="kg")

        _lot(db, "lot-reko-milk", toika.id, "prod-reko-milk", "Raw milk", "dairy",
             12.0, 1.4, 640, 1.2, nurmijarvi.place, unit="L", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end, featured=True)
        _lot(db, "lot-reko-veg", nodes["node-lohenoja"].id, "prod-reko-veg", "Organic vegetables",
             "greens", 15.0, 3.5, 250, 0.2, nurmijarvi.place, unit="kg", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-lamb", nodes["node-airikkala"].id, "prod-reko-lamb", "Organic lamb",
             "meat", 4.0, 22.0, 2400, 10.0, nurmijarvi.place, unit="kg", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-eggs", nodes["node-mantymaeki"].id, "prod-reko-eggs", "Organic eggs",
             "eggs", 30.0, 0.50, 1430, 1.8, hyvinkaa.place, unit="kpl", drop_id=drop_hy.id,
             available_from=hy_start, available_until=hy_end)
        _lot(db, "lot-reko-juice", nodes["node-wennborg"].id, "prod-reko-juice", "Berry juice",
             "preserve", 10.0, 6.0, 180, 0.2, hyvinkaa.place, unit="L", drop_id=drop_hy.id,
             available_from=hy_start, available_until=hy_end)
        _lot(db, "lot-reko-kale", kariniemi.id, "prod-reko-kale", "Lehtikaali (kale)", "greens",
             6.0, 4.0, 490, 0.4, hyvinkaa.place, unit="kg", drop_id=drop_hy.id,
             available_from=hy_start, available_until=hy_end)
        _lot(db, "lot-reko-eggs-k", kariniemi.id, "prod-reko-eggs-k", "Farm eggs", "eggs",
             24.0, 0.40, 1430, 2.1, hyvinkaa.place, unit="kpl", drop_id=drop_hy.id,
             available_from=hy_start, available_until=hy_end)
        _lot(db, "lot-reko-beef", toika.id, "prod-reko-beef", "Farm beef", "meat",
             6.0, 18.0, 2500, 12.0, nurmijarvi.place, unit="kg", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-ostrich", nodes["node-ketola"].id, "prod-reko-ostrich", "Ostrich eggs",
             "eggs", 4.0, 8.0, 1400, 2.0, nurmijarvi.place, unit="kpl", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-strawberry-m", nodes["node-mattila"].id, "prod-reko-strawberry-m",
             "Organic strawberries", "berries", 8.0, 10.0, 320, 0.3, nurmijarvi.place,
             unit="kg", drop_id=drop_nj.id, available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-strawberry-w", nodes["node-wennborg"].id, "prod-reko-strawberry-w",
             "Farm strawberries", "berries", 10.0, 9.0, 320, 0.3, hyvinkaa.place,
             unit="kg", drop_id=drop_hy.id, available_from=hy_start, available_until=hy_end)
        _lot(db, "lot-reko-raspberry", nodes["node-myllymaa"].id, "prod-reko-raspberry", "Raspberries",
             "berries", 5.0, 12.0, 520, 0.2, nurmijarvi.place, unit="kg", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-honey", nodes["node-myllymaa"].id, "prod-reko-honey", "Farm honey",
             "preserve", 6.0, 8.0, 3040, 0.3, nurmijarvi.place, unit="kpl", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-cabbage", nodes["node-vaihia"].id, "prod-reko-cabbage", "Cabbage",
             "greens", 20.0, 1.2, 250, 0.2, nurmijarvi.place, unit="kg", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-flakes", nodes["node-kranni"].id, "prod-reko-flakes", "Oat flakes",
             "preserve", 15.0, 3.5, 3700, 0.4, nurmijarvi.place, unit="kg", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-flour", nodes["node-knehtila"].id, "prod-reko-flour", "Organic flour",
             "preserve", 12.0, 2.8, 3600, 0.4, hyvinkaa.place, unit="kg", drop_id=drop_hy.id,
             available_from=hy_start, available_until=hy_end)
        _lot(db, "lot-reko-milk-y", nodes["node-ylisjoki"].id, "prod-reko-milk-y", "Tinkimaito",
             "dairy", 10.0, 1.5, 640, 1.2, nurmijarvi.place, unit="L", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-veg-hy", nodes["node-lohenoja"].id, "prod-reko-veg-hy", "Organic vegetables",
             "greens", 12.0, 3.5, 250, 0.2, hyvinkaa.place, unit="kg", drop_id=drop_hy.id,
             available_from=hy_start, available_until=hy_end)
        _lot(db, "lot-reko-yarn", nodes["node-aliolli"].id, "prod-reko-yarn", "Alpaca yarn",
             "preserve", 4.0, 18.0, 0, 0.1, nurmijarvi.place, unit="kpl", drop_id=drop_nj.id,
             available_from=nj_start, available_until=nj_end)
        _lot(db, "lot-reko-eggs-tuiskula", nodes["node-tuiskula"].id, "prod-reko-eggs-tuiskula",
             "Pasture eggs", "eggs", 24.0, 0.45, 1430, 1.6, siuntio.place, unit="kpl",
             drop_id=drop_si.id, available_from=si_start, available_until=si_end)
        _lot(db, "lot-reko-veg-tuiskula", nodes["node-tuiskula"].id, "prod-reko-veg-tuiskula",
             "Farm vegetables", "greens", 8.0, 3.5, 250, 0.2, siuntio.place, unit="kg",
             drop_id=drop_si.id, available_from=si_start, available_until=si_end)
        _lot(db, "lot-reko-haskap", nodes["node-isfarmi"].id, "prod-reko-haskap", "Haskap (hunajamarja)",
             "berries", 5.0, 14.0, 470, 0.3, siuntio.place, unit="kg",
             drop_id=drop_si.id, available_from=si_start, available_until=si_end)
        _lot(db, "lot-reko-tyrni", nodes["node-isfarmi"].id, "prod-reko-tyrni", "Tyrni",
             "berries", 4.0, 16.0, 820, 0.3, siuntio.place, unit="kg",
             drop_id=drop_si.id, available_from=si_start, available_until=si_end)

        db.commit()
        print("Seeded Satokori" if reset else "Ensured Satokori marketplace")
        print()
        print("Organizer (password: farmgate)")
        print("  wkariniemi@proton.me   Kariniemi Farms (claimed, Live)")
        print()
        print("Unclaimed farms — farmer taps This is my farm on Map; admin approves:")
        for node_id, name, *_rest in farms:
            print(f"  {name}")
        print()
        print("Unclaimed REKO rings — ring admin logs in, then taps This is my REKO ring:")
        print(f"  {hyvinkaa.name}  {hy_start:%a %H:%M}–{hy_end:%H:%M}  {hyvinkaa.place}")
        print(f"  {nurmijarvi.name}  {nj_start:%a %H:%M}–{nj_end:%H:%M}  {nurmijarvi.place}")
        print(f"  {siuntio.name}  {si_start:%a %H:%M}–{si_end:%H:%M}  {siuntio.place}")
        print()
        print("Marketplace: unclaimed lots are Demo. Claimed farms show Live. Featured: Toikantila raw milk at REKO Nurmijärvi.")
    finally:
        db.close()


def ensure():
    seed(reset=False)


if __name__ == "__main__":
    seed()
