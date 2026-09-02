from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.db import engine
from app.models import *  # noqa: ensure all models registered before create_all
from app.models.ruuvi_reading import RuuviReading  # noqa
from app.models.flare import DemandFlare  # noqa
from app.db import Base
from app.routes import tips, transactions, auth, nodes, produce, agent, square, onboard, asks, push, admin, rings

Base.metadata.create_all(bind=engine)


def _ensure_listing_unit():
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "listings" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("listings")}
    if "unit" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE listings ADD COLUMN unit VARCHAR DEFAULT 'kg'"))
    if "perpetual" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE listings ADD COLUMN perpetual BOOLEAN DEFAULT 0"))
    if "demo" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE listings ADD COLUMN demo BOOLEAN DEFAULT 0"))
    if "featured" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE listings ADD COLUMN featured BOOLEAN DEFAULT 0"))
    if "drop_id" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE listings ADD COLUMN drop_id VARCHAR"))


def _ensure_ask_pickup_columns():
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "pickup_asks" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("pickup_asks")}
    with engine.begin() as conn:
        if "picked_up_by" not in cols:
            conn.execute(text("ALTER TABLE pickup_asks ADD COLUMN picked_up_by VARCHAR"))
        if "picked_up_at" not in cols:
            conn.execute(text("ALTER TABLE pickup_asks ADD COLUMN picked_up_at DATETIME"))
        if "buyer_verified_at" not in cols:
            conn.execute(text("ALTER TABLE pickup_asks ADD COLUMN buyer_verified_at DATETIME"))
        if "farmer_verified_at" not in cols:
            conn.execute(text("ALTER TABLE pickup_asks ADD COLUMN farmer_verified_at DATETIME"))
        if "acknowledged_at" not in cols:
            conn.execute(text("ALTER TABLE pickup_asks ADD COLUMN acknowledged_at DATETIME"))


def _ensure_node_claim_columns():
    import secrets
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "nodes" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("nodes")}
    with engine.begin() as conn:
        if "claim_id" not in cols:
            conn.execute(text("ALTER TABLE nodes ADD COLUMN claim_id VARCHAR"))
        added_claimed_at = "claimed_at" not in cols
        if added_claimed_at:
            conn.execute(text("ALTER TABLE nodes ADD COLUMN claimed_at DATETIME"))
        # Backfill claim_id for any node that doesn't have one yet
        existing = conn.execute(text("SELECT id FROM nodes WHERE claim_id IS NULL")).fetchall()
        for (node_id,) in existing:
            conn.execute(
                text("UPDATE nodes SET claim_id = :claim_id WHERE id = :node_id"),
                {"claim_id": secrets.token_urlsafe(10), "node_id": node_id},
            )
        # One-time only: nodes that predated claimed_at were already owned.
        # Do not repeat this on later startups — unclaimed onboarded farms keep claimed_at NULL.
        if added_claimed_at:
            conn.execute(text(
                "UPDATE nodes SET claimed_at = CURRENT_TIMESTAMP"
                " WHERE owner_id IS NOT NULL AND claimed_at IS NULL"
            ))


def _ensure_ring_columns():
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "rings" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("rings")}
    with engine.begin() as conn:
        if "facebook_url" not in cols:
            conn.execute(text("ALTER TABLE rings ADD COLUMN facebook_url VARCHAR DEFAULT ''"))
        if "claim_id" not in cols:
            conn.execute(text("ALTER TABLE rings ADD COLUMN claim_id VARCHAR"))
        if "claimed_at" not in cols:
            conn.execute(text("ALTER TABLE rings ADD COLUMN claimed_at DATETIME"))
        if "admin_id" not in cols:
            conn.execute(text("ALTER TABLE rings ADD COLUMN admin_id VARCHAR"))


_ensure_listing_unit()
_ensure_ask_pickup_columns()
_ensure_node_claim_columns()
_ensure_ring_columns()

app = FastAPI(title="Satokori", version="0.3.0")
app.include_router(auth.router)
app.include_router(nodes.router)
app.include_router(tips.router)
app.include_router(transactions.router)
app.include_router(produce.router)
app.include_router(agent.router)
app.include_router(square.router)
app.include_router(onboard.router)
app.include_router(asks.router)
app.include_router(push.router)
app.include_router(admin.router)
app.include_router(rings.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/square.html")


@app.get("/r/{token}")
def farmer_reply_page(token: str):
    return FileResponse("static/reply.html")


@app.get("/sw.js")
def service_worker():
    return FileResponse(
        "static/sw.js",
        media_type="text/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/console")
def console():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
