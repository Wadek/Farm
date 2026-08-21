from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.db import engine
from app.models import *  # noqa: ensure all models registered before create_all
from app.models.ruuvi_reading import RuuviReading  # noqa
from app.models.flare import DemandFlare  # noqa
from app.db import Base
from app.routes import tips, transactions, auth, nodes, produce, agent, square, onboard, asks

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


_ensure_listing_unit()

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
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/square.html")


@app.get("/r/{token}")
def farmer_reply_page(token: str):
    return FileResponse("static/reply.html")


@app.get("/console")
def console():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
