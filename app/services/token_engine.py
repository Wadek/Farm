import math
from dataclasses import dataclass

# Finland context constants — Hyvinkää baseline
KWH_PRICE_EUR = 0.22          # €/kWh
CARBON_VALUE_EUR = 0.09       # €/kg CO2 (€90/tonne)
KCAL_TO_KWH = 0.001162        # conversion factor
KCAL_DENSITY_MULTIPLIER = 10  # energy density multiplier per spec
IMPORT_DISTANCE_KM = 2500.0   # avg industrial supply chain distance to Finland
STORE_TRANSPORT_FACTOR = 0.00015   # kg CO2 per km per kg of produce
LOCAL_TRANSPORT_FACTOR = 0.00005   # kg CO2 per km per kg (local vehicle)
DECAY_RATE = 0.15             # hyperlocal signal boost decay coefficient


@dataclass
class TokenResult:
    co2_saved_kg: float
    kwh_equiv: float
    energy_value_eur: float
    eco_value_eur: float
    myc_tokens: float
    distance_km: float
    is_walking: bool


def calculate(
    kcal_per_kg: float,
    store_co2_per_kg: float,
    local_co2_per_kg: float,
    mass_kg: float,
    distance_km: float,
    is_walking: bool,
) -> TokenResult:
    """
    Port of HyphaeLogic.calculateNutrientFlow from mycelium (Dart).
    Calculates MYC tokens minted for a hyperlocal food exchange.

    Token value = (energy value of food) + (ecological value of CO2 saved)
    boosted by a distance decay factor — closer trades earn more.
    """
    # 1. Carbon: industrial supply chain vs local delivery
    store_transport = IMPORT_DISTANCE_KM * STORE_TRANSPORT_FACTOR * mass_kg
    total_store_co2 = (store_co2_per_kg * mass_kg) + store_transport

    local_transport = 0.0 if is_walking else (distance_km * LOCAL_TRANSPORT_FACTOR * mass_kg)
    total_local_co2 = (local_co2_per_kg * mass_kg) + local_transport

    co2_saved = total_store_co2 - total_local_co2

    # 2. Energy value of the food exchanged
    food_kwh = (kcal_per_kg * KCAL_DENSITY_MULTIPLIER * mass_kg) * KCAL_TO_KWH
    energy_value = food_kwh * KWH_PRICE_EUR

    # 3. Ecological value — only positive CO2 savings count
    eco_value = max(0.0, co2_saved) * CARBON_VALUE_EUR

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
    )
