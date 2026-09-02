from sqlalchemy import Column, String, Float, Boolean, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class ListingStatus(str, enum.Enum):
    active = "active"
    reserved = "reserved"
    sold_out = "sold_out"
    completed = "completed"


class Listing(Base):
    __tablename__ = "listings"

    id = Column(String, primary_key=True)
    node_id = Column(String, ForeignKey("nodes.id"), nullable=False)
    produce_id = Column(String, ForeignKey("produce.id"), nullable=False)
    quantity_kg = Column(Float, nullable=False)
    unit = Column(String, default="kg")  # kg | L | kpl | box | bunch
    price_per_kg = Column(Float, default=0.0)   # price per unit
    pickup_point = Column(String, nullable=False)  # defaults to node location
    is_free = Column(Boolean, default=False)
    available_from = Column(DateTime, nullable=True)
    available_until = Column(DateTime, nullable=True)
    perpetual = Column(Boolean, default=False)
    demo = Column(Boolean, default=False)
    featured = Column(Boolean, default=False)
    drop_id = Column(String, ForeignKey("ring_drops.id"), nullable=True, index=True)
    image_url = Column(String, nullable=True)
    private = Column(Boolean, default=False)
    privacy_v = Column(String, nullable=True)
    privacy_iv = Column(String, nullable=True)
    privacy_ct = Column(String, nullable=True)
    status = Column(Enum(ListingStatus), default=ListingStatus.active)
    created_at = Column(DateTime, server_default=func.now())

    node = relationship("Node", back_populates="listings")
    produce = relationship("Produce", back_populates="listings")
    drop = relationship("RingDrop", back_populates="listings")
    transactions = relationship("Transaction", back_populates="listing")
