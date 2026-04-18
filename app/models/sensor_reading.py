from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, func
from app.db import Base


class SensorReading(Base):
    """
    Unified append-only sensor reading table.
    Handles all sensor sources: Ruuvi, Ajax, manual, future integrations.
    """
    __tablename__ = "sensor_readings"

    id = Column(String, primary_key=True)
    node_id = Column(String, ForeignKey("nodes.id"), nullable=False)

    source = Column(String, nullable=False)       # "ruuvi", "ajax", "manual"
    sensor_type = Column(String, nullable=False)  # "temperature", "door", "motion", "fence", "alarm"
    device_id = Column(String, nullable=True)     # MAC, Ajax device ID, etc.
    device_name = Column(String, nullable=True)   # human-readable label

    value = Column(Float, nullable=True)          # primary numeric value
    unit = Column(String, nullable=True)          # "°C", "%", "hPa", "V"
    status = Column(String, nullable=True)        # "open", "closed", "triggered", "ok"

    data_json = Column(Text, nullable=True)       # full raw payload

    recorded_at = Column(DateTime, server_default=func.now())
