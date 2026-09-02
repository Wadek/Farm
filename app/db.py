from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings


def _sqlite_connect_args(url: str) -> dict:
    if not url.startswith("sqlite"):
        return {}
    if ":memory:" not in url and ":///" in url:
        path = Path(url.split(":///", 1)[1])
        if path.parent and str(path.parent) not in ("", "."):
            path.parent.mkdir(parents=True, exist_ok=True)
    return {"check_same_thread": False}


engine = create_engine(settings.database_url, connect_args=_sqlite_connect_args(settings.database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
