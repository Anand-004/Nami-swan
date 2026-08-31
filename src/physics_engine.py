"""Physics engine: hydrodynamic resistance model, speed-over-ground adjustment,
fuel burn, and CO2 emission calculations."""

from __future__ import annotations

import math
from typing import List, Optional

from .models import VesselSpec, WeatherPoint, bearing_deg


def _wind_resistance_factor(
    wind_speed_kts: float,
    wind_dir_deg: float,
    heading_deg: float,
) -> float:
    """Estimate added resistance multiplier due to wind.

    Headwind increases resistance; tailwind decreases it slightly.
    Uses a simplified cosine model.
    """
    relative_angle = math.radians(wind_dir_deg - heading_deg)
    # Component of wind along vessel heading (positive = headwind)
    headwind_component = wind_speed_kts * math.cos(relative_angle)
    # Empirical: every 10 kts of headwind adds ~3% resistance
    factor = 1.0 + 0.003 * headwind_component
    return max(factor, 0.85)  # tailwind can reduce, but cap benefit


def _wave_resistance_factor(wave_height_m: float) -> float:
    """Added resistance from significant wave height.

    Based on simplified Townsin-Kwon formula:
    ~2% added resistance per metre of wave height.
    """
    return 1.0 + 0.02 * wave_height_m ** 1.5


def compute_speed_over_ground(
    vessel_speed_kts: float,
    heading_deg: float,
    current_speed_kts: float,
    current_dir_deg: float,
) -> float:
    """Calculate effective speed over ground (SOG) given ocean current.

    Current vector is added to vessel velocity vector.
    """
    # Current component along vessel heading
    relative_angle = math.radians(current_dir_deg - heading_deg)
    current_along = current_speed_kts * math.cos(relative_angle)
    sog = vessel_speed_kts + current_along
    return max(sog, 0.5)  # never negative / stalled


def compute_fuel_burn(
    vessel: VesselSpec,
    distance_nm: float,
    speed_kts: float,
    wind_speed_kts: float = 0.0,
    wind_dir_deg: float = 0.0,
    wave_height_m: float = 0.0,
    heading_deg: float = 0.0,
) -> float:
    """Compute fuel burned (metric tons) over a segment.

    Uses the admiralty coefficient approximation:
        fuel_rate ∝ (actual_speed / design_speed) ^ 3

    Then adjusted for wind and wave resistance factors.
    """
    if speed_kts <= 0 or distance_nm <= 0:
        return 0.0

    # Speed ratio cubed (admiralty law)
    speed_ratio = speed_kts / vessel.design_speed_knots
    base_rate_mt_hr = vessel.base_fuel_rate_mt_day / 24.0
    fuel_rate = base_rate_mt_hr * (speed_ratio ** 3)

    # Environmental resistance multipliers
    wind_factor = _wind_resistance_factor(wind_speed_kts, wind_dir_deg, heading_deg)
    wave_factor = _wave_resistance_factor(wave_height_m)
    fuel_rate *= wind_factor * wave_factor

    # Duration of this segment
    hours = distance_nm / speed_kts
    return fuel_rate * hours


def compute_co2(fuel_burn_mt: float, emission_factor: float) -> float:
    """CO2 emissions from fuel burned: CO2 = fuel × emission_factor."""
    return fuel_burn_mt * emission_factor


def optimal_speed_for_segment(
    vessel: VesselSpec,
    distance_nm: float,
    remaining_hours: float,
) -> float:
    """Choose an economically sensible speed within vessel limits.

    Tries to arrive on time without exceeding max speed.
    Falls back to design speed if plenty of time remains.
    """
    if remaining_hours <= 0:
        return vessel.max_speed_knots

    needed_speed = distance_nm / remaining_hours
    speed = max(vessel.min_speed_knots, min(needed_speed, vessel.max_speed_knots))
    return round(speed, 2)
