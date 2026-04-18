from sqlalchemy import Column, String, Float, DateTime, Text, func
from app.db import Base


class RegionalConfig(Base):
    """
    Weekly snapshot of regional constants used by the token engine.
    One row per region per week — append-only, never updated in place.
    """
    __tablename__ = "regional_configs"

    id = Column(String, primary_key=True)
    country_code = Column(String, nullable=False)       # "FI", "SE", etc.
    region = Column(String, nullable=True)              # "Uusimaa", etc.
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    # Electricity
    kwh_spot_eur = Column(Float, nullable=False)        # current hour spot price
    kwh_weekly_avg_eur = Column(Float, nullable=True)   # 7-day average
    grid_intensity_kg_co2_per_kwh = Column(Float, nullable=False)

    # Carbon
    carbon_value_eur_per_kg = Column(Float, nullable=False)  # EU ETS per kg CO2

    # Supply chain — PLACEHOLDER, future supply chain engine needed for accuracy
    import_distance_km = Column(Float, nullable=False)
    store_transport_factor = Column(Float, nullable=False)
    local_transport_factor = Column(Float, nullable=False)

    fetched_at = Column(DateTime, server_default=func.now())
    valid_until = Column(DateTime, nullable=False)
    source_notes = Column(Text, nullable=True)
