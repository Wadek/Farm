from sqlalchemy import Column, String, Enum, DateTime, Boolean, func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class UserRole(str, enum.Enum):
    organizer = "organizer"
    farmer = "farmer"
    buyer = "buyer"
    ring_admin = "ring_admin"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    phone = Column(String, default="")
    privacy = Column(Boolean, default=False)
    disabled = Column(Boolean, default=False)
    last_sync_at = Column(DateTime, nullable=True)
    lockbox_v = Column(String, nullable=True)
    lockbox_iv = Column(String, nullable=True)
    lockbox_ct = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    nodes = relationship("Node", back_populates="owner", foreign_keys="Node.owner_id")
    messages_sent = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    api_keys = relationship("ApiKey", back_populates="user")
