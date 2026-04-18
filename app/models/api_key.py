import secrets
import hashlib
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    label = Column(String, default="")
    key_hash = Column(String, nullable=False, index=True)
    prefix = Column(String, nullable=False)   # first 8 chars for display
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="api_keys")

    @staticmethod
    def generate() -> tuple[str, str]:
        """Returns (plaintext_key, hash). Store the hash; return plaintext once."""
        raw = "farm_" + secrets.token_urlsafe(32)
        h = hashlib.sha256(raw.encode()).hexdigest()
        return raw, h

    @staticmethod
    def hash(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()
