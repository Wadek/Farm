from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base


class JournalSession(Base):
    __tablename__ = "journal_sessions"

    id = Column(String, primary_key=True)
    context_json = Column(Text, nullable=False)
    node_id = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    entries = relationship("JournalEntry", back_populates="session")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("journal_sessions.id"), nullable=False)
    question = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending | completed | failed
    created_at = Column(DateTime, server_default=func.now())

    session = relationship("JournalSession", back_populates="entries")
