from sqlalchemy import Column, String, Float, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class FlareStatus(str, enum.Enum):
    open = "open"
    matched = "matched"
    closed = "closed"


class DemandFlare(Base):
    """A buyer's 'need' signal — the mycelium demand vacuum."""

    __tablename__ = "demand_flares"

    id = Column(String, primary_key=True)
    buyer_id = Column(String, ForeignKey("users.id"), nullable=False)
    item = Column(String, nullable=False)
    quantity_note = Column(String, default="")
    radius_km = Column(Float, default=20.0)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    status = Column(Enum(FlareStatus), default=FlareStatus.open)
    created_at = Column(DateTime, server_default=func.now())

    buyer = relationship("User")
