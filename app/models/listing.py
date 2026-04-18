from sqlalchemy import Column, String, Float, Boolean, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class ListingStatus(str, enum.Enum):
    active = "active"
    reserved = "reserved"
    completed = "completed"


class Listing(Base):
    __tablename__ = "listings"

    id = Column(String, primary_key=True)
    node_id = Column(String, ForeignKey("nodes.id"), nullable=False)
    produce_id = Column(String, ForeignKey("produce.id"), nullable=False)
    quantity_kg = Column(Float, nullable=False)
    price_per_kg = Column(Float, default=0.0)   # 0 = free / barter
    pickup_point = Column(String, nullable=False)  # defaults to node location
    is_free = Column(Boolean, default=False)
    status = Column(Enum(ListingStatus), default=ListingStatus.active)
    created_at = Column(DateTime, server_default=func.now())

    node = relationship("Node", back_populates="listings")
    produce = relationship("Produce", back_populates="listings")
    transactions = relationship("Transaction", back_populates="listing")
