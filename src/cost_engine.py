"""Cost engine: computes per-segment cost incorporating fuel, CO2, weather risk,
delay penalties, and operational costs."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from .models import PenaltyConfig, VesselSpec, WeatherPoint, haversine_nm, bearing_deg
from .physics_engine import (
    compute_co2,
    compute_fuel_burn,
    compute_speed_over_ground,
    optimal_speed_for_segment,
)


def compute_segment_cost(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    current_time: datetime,
    deadline: datetime,
    vessel: VesselSpec,
    penalties: PenaltyConfig,
    weather: Optional[WeatherPoint] = None,
    remaining_distance_nm: float = 0.0,
) -> dict:
    """Compute the full cost of traversing one segment from (lat1,lon1) to (lat2,lon2).

    Returns a dict with:
        distance_nm, speed_kts, sog_kts, duration_hours, fuel_mt, co2_mt,
        fuel_cost, co2_cost, op_cost, delay_cost, weather_risk, total_cost,
        arrival_time
    """
    distance = haversine_nm(lat1, lon1, lat2, lon2)
    heading = bearing_deg(lat1, lon1, lat2, lon2)

    # Time budget
    remaining_hours = max(
        (deadline - current_time).total_seconds() / 3600.0, 0.1
    )
    total_remaining_nm = remaining_distance_nm + distance

    # Choose speed
    speed = optimal_speed_for_segment(vessel, total_remaining_nm, remaining_hours)

    # Weather adjustments
    wind_speed = weather.wind_speed_kts if weather else 0.0
    wind_dir = weather.wind_dir_deg if weather else 0.0
    wave_height = weather.wave_height_m if weather else 0.0
    current_spd = weather.current_speed_kts if weather else 0.0
    current_dir = weather.current_dir_deg if weather else 0.0

    # Speed over ground
    sog = compute_speed_over_ground(speed, heading, current_spd, current_dir)

    # Duration
    if sog <= 0:
        sog = 0.5
    duration_hours = distance / sog

    # Fuel & emissions
    fuel_mt = compute_fuel_burn(
        vessel, distance, speed,
        wind_speed, wind_dir, wave_height, heading,
    )
    co2_mt = compute_co2(fuel_mt, penalties.co2_factor_vlsfo)

    # --- Cost components ---
    fuel_cost = fuel_mt * penalties.fuel_price_per_mt
    co2_cost = co2_mt * penalties.co2_cost_per_mt
    op_cost = duration_hours * penalties.operational_hourly_rate

    # Delay penalty (prorated from this segment's share)
    arrival_time = current_time + timedelta(hours=duration_hours)
    delay_hours = max(
        (arrival_time - deadline).total_seconds() / 3600.0, 0.0
    )
    delay_cost = delay_hours * penalties.delay_penalty_hourly

    # Weather risk penalty
    weather_risk = 0.0
    if weather:
        if wave_height > vessel.max_wave_height_tolerance_m:
            # Severe — heavily penalise to force avoidance
            weather_risk += 50000.0 * penalties.storm_risk_multiplier
        elif wave_height > 4.0:
            weather_risk += 5000.0 * (wave_height - 4.0) * penalties.storm_risk_multiplier
        if wind_speed > 34:  # gale force (Beaufort 8+)
            weather_risk += 10000.0 * penalties.storm_risk_multiplier

    total_cost = fuel_cost + co2_cost + op_cost + delay_cost + weather_risk

    return {
        "distance_nm": distance,
        "speed_kts": speed,
        "sog_kts": sog,
        "duration_hours": duration_hours,
        "fuel_mt": fuel_mt,
        "co2_mt": co2_mt,
        "fuel_cost": fuel_cost,
        "co2_cost": co2_cost,
        "op_cost": op_cost,
        "delay_cost": delay_cost,
        "weather_risk": weather_risk,
        "total_cost": total_cost,
        "arrival_time": arrival_time,
    }
