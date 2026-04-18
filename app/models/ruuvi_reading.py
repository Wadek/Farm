from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, func
from app.db import Base


class RuuviReading(Base):
    """Append-only table — one row per sensor reading, never updated."""
    __tablename__ = "ruuvi_readings"

    id = Column(String, primary_key=True)
    node_id = Column(String, ForeignKey("nodes.id"), nullable=False)
    mac = Column(String, nullable=True)           # Ruuvi tag MAC address
    temperature_c = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    pressure_hpa = Column(Float, nullable=True)
    battery_v = Column(Float, nullable=True)
    rssi = Column(Integer, nullable=True)
    recorded_at = Column(DateTime, server_default=func.now())
