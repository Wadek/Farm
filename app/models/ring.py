from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base


class Ring(Base):
    """A REKO-style pre-order ring: shared drop place and clock."""

    __tablename__ = "rings"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    place = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    notes = Column(String, default="")
    facebook_url = Column(String, default="")
    claim_id = Column(String, unique=True, nullable=True, index=True)
    claimed_at = Column(DateTime, nullable=True)
    admin_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    drops = relationship("RingDrop", back_populates="ring")
    admin = relationship("User")


class RingDrop(Base):
    """One pickup occurrence of a ring."""

    __tablename__ = "ring_drops"

    id = Column(String, primary_key=True)
    ring_id = Column(String, ForeignKey("rings.id"), nullable=False, index=True)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    order_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    ring = relationship("Ring", back_populates="drops")
    listings = relationship("Listing", back_populates="drop")
