from fastapi import FastAPI
from app.db import engine
from app.models import *  # noqa: ensure all models registered before create_all
from app.db import Base
from app.routes import tips, transactions, auth

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Farm Network API", version="0.1.0")
app.include_router(auth.router)
app.include_router(tips.router)
app.include_router(transactions.router)


@app.get("/health")
def health():
    return {"status": "ok"}
