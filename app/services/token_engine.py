import math
from dataclasses import dataclass
from typing import Optional

# Physical constants — these do not change with region
KCAL_TO_KWH = 0.001162
KCAL_DENSITY_MULTIPLIER = 10
DECAY_RATE = 0.15  # hyperlocal signal boost decay coefficient

# Finland fallback constants — used only when no RegionalConstants provided
# These are replaced by regional_service.fetch_constants() in production
_FI_FALLBACK_KWH_PRICE = 0.12
_FI_FALLBACK_CARBON_VALUE = 0.065
_FI_FALLBACK_IMPORT_DISTANCE = 2500.0
_FI_FALLBACK_STORE_TRANSPORT = 0.00015   # PLACEHOLDER: needs supply chain engine
_FI_FALLBACK_LOCAL_TRANSPORT = 0.00005   # PLACEHOLDER: needs supply chain engine


@dataclass
class RegionalConstants:
    kwh_price_eur: float
    carbon_value_eur_per_kg: float
    import_distance_km: float
    store_transport_factor: float
    local_transport_factor: float


@dataclass
class TokenResult:
    co2_saved_kg: float
    kwh_equiv: float
    energy_value_eur: float
    eco_value_eur: float
    myc_tokens: float
    distance_km: float
    is_walking: bool
    constants_used: RegionalConstants


def _fi_fallback() -> RegionalConstants:
    return RegionalConstants(
        kwh_price_eur=_FI_FALLBACK_KWH_PRICE,
        carbon_value_eur_per_kg=_FI_FALLBACK_CARBON_VALUE,
        import_distance_km=_FI_FALLBACK_IMPORT_DISTANCE,
        store_transport_factor=_FI_FALLBACK_STORE_TRANSPORT,
        local_transport_factor=_FI_FALLBACK_LOCAL_TRANSPORT,
    )


def constants_from_regional(regional) -> RegionalConstants:
    """Convert a RegionalConfig DB record to a RegionalConstants dataclass."""
    return RegionalConstants(
        kwh_price_eur=regional.kwh_spot_eur,
        carbon_value_eur_per_kg=regional.carbon_value_eur_per_kg,
        import_distance_km=regional.import_distance_km,
        store_transport_factor=regional.store_transport_factor,
        local_transport_factor=regional.local_transport_factor,
    )


def calculate(
    kcal_per_kg: float,
    store_co2_per_kg: float,
    local_co2_per_kg: float,
    mass_kg: float,
    distance_km: float,
    is_walking: bool,
    constants: Optional[RegionalConstants] = None,
) -> TokenResult:
    """
    Calculate MYC tokens minted for a hyperlocal food exchange.

    Port of HyphaeLogic.calculateNutrientFlow (mycelium, Dart).
    Token value = (energy value of food) + (ecological value of CO2 saved)
    boosted by distance decay — closer trades earn more.

    Pass a RegionalConstants instance for accurate regional pricing.
    Falls back to Finland defaults if not provided.
    """
    c = constants or _fi_fallback()

    # 1. Carbon: industrial supply chain vs local delivery
    store_transport = c.import_distance_km * c.store_transport_factor * mass_kg
    total_store_co2 = (store_co2_per_kg * mass_kg) + store_transport

    local_transport = 0.0 if is_walking else (distance_km * c.local_transport_factor * mass_kg)
    total_local_co2 = (local_co2_per_kg * mass_kg) + local_transport

    co2_saved = total_store_co2 - total_local_co2

    # 2. Energy value of the food exchanged
    food_kwh = (kcal_per_kg * KCAL_DENSITY_MULTIPLIER * mass_kg) * KCAL_TO_KWH
    energy_value = food_kwh * c.kwh_price_eur

    # 3. Ecological value — only positive CO2 savings count
    eco_value = max(0.0, co2_saved) * c.carbon_value_eur_per_kg

    # 4. Hyperlocal signal boost — exponential decay with distance
    decay_factor = math.exp(-DECAY_RATE * distance_km)
    myc_tokens = (energy_value + eco_value) * (1 + decay_factor)

    return TokenResult(
        co2_saved_kg=co2_saved,
        kwh_equiv=food_kwh,
        energy_value_eur=energy_value,
        eco_value_eur=eco_value,
        myc_tokens=myc_tokens,
        distance_km=distance_km,
        is_walking=is_walking,
        constants_used=c,
    )
