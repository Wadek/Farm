from sqlalchemy import Column, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=False)
    buyer_id = Column(String, ForeignKey("users.id"), nullable=False)
    quantity_kg = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=False)
    is_walking = Column(String, default=False)
    co2_saved_kg = Column(Float, default=0.0)
    kwh_equiv = Column(Float, default=0.0)
    myc_tokens_minted = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())

    listing = relationship("Listing", back_populates="transactions")
    buyer = relationship("User", foreign_keys=[buyer_id])
