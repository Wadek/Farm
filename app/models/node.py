from sqlalchemy import Column, String, Float, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db import Base
import enum


class NodeType(str, enum.Enum):
    garden_bed = "garden_bed"
    backyard = "backyard"
    hobby_farm = "hobby_farm"
    farm = "farm"


class Node(Base):
    __tablename__ = "nodes"

    id = Column(String, primary_key=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum(NodeType), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    description = Column(String, default="")
    area_m2 = Column(Float, default=0.0)
    myc_tokens = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())

    owner = relationship("User", back_populates="nodes")
    produce = relationship("Produce", back_populates="node")
    listings = relationship("Listing", back_populates="node")
