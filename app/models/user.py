from sqlalchemy import Column, String, Enum, DateTime, func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class UserRole(str, enum.Enum):
    farmer = "farmer"
    buyer = "buyer"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    nodes = relationship("Node", back_populates="owner")
    messages_sent = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    api_keys = relationship("ApiKey", back_populates="user")
