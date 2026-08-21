import enum
from sqlalchemy import Column, String, Float, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base


class AskStatus(str, enum.Enum):
    asked = "asked"
    offered = "offered"
    confirmed = "confirmed"
    picked_up = "picked_up"
    declined = "declined"
    withdrawn = "withdrawn"


class PickupAsk(Base):
    """Neighbor call: can I pick this up? Farmer answers with a time."""

    __tablename__ = "pickup_asks"

    id = Column(String, primary_key=True)
    token = Column(String, unique=True, nullable=False, index=True)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=False)
    buyer_id = Column(String, ForeignKey("users.id"), nullable=False)
    farmer_id = Column(String, ForeignKey("users.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String, default="kg")
    note = Column(String, default="")
    status = Column(Enum(AskStatus), default=AskStatus.asked)
    offer_text = Column(String, default="")
    picked_up_by = Column(String, nullable=True)
    picked_up_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    listing = relationship("Listing")
    buyer = relationship("User", foreign_keys=[buyer_id])
    farmer = relationship("User", foreign_keys=[farmer_id])


class SmsLog(Base):
    __tablename__ = "sms_log"

    id = Column(String, primary_key=True)
    direction = Column(String, nullable=False)  # out | in
    phone = Column(String, default="")
    body = Column(String, nullable=False)
    ask_id = Column(String, ForeignKey("pickup_asks.id"), nullable=True)
    provider = Column(String, default="log")
    created_at = Column(DateTime, server_default=func.now())
