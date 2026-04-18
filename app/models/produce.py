from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base


class Produce(Base):
    __tablename__ = "produce"

    id = Column(String, primary_key=True)
    node_id = Column(String, ForeignKey("nodes.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    quantity_kg = Column(Float, default=0.0)
    kcal_per_kg = Column(Float, default=0.0)
    co2_kg_per_kg = Column(Float, default=0.0)   # CO2 cost of this produce locally
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    node = relationship("Node", back_populates="produce")
    listings = relationship("Listing", back_populates="produce")
