from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=False)
    listing_id = Column(String, ForeignKey("listings.id"), nullable=True)
    body = Column(String, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    sender = relationship("User", foreign_keys=[sender_id], back_populates="messages_sent")
    recipient = relationship("User", foreign_keys=[recipient_id])
    listing = relationship("Listing")
