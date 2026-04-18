from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.db import engine
from app.models import *  # noqa: ensure all models registered before create_all
from app.models.ruuvi_reading import RuuviReading  # noqa
from app.db import Base
from app.routes import tips, transactions, auth, nodes

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Farm Network API", version="0.1.0")
app.include_router(auth.router)
app.include_router(nodes.router)
app.include_router(tips.router)
app.include_router(transactions.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
