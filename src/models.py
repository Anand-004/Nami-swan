"""Data models for vessel specifications, voyage requests, waypoints, and weather."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class VesselSpec:
    """Mechanical and operational parameters of a cargo vessel."""
    vessel_id: str
    vessel_type: str
    design_speed_knots: float
    min_speed_knots: float
    max_speed_knots: float
    rpm_min: int
    rpm_max: int
    fuel_type: str
    base_fuel_rate_mt_day: float       # metric tons per day at design speed
    max_wave_height_tolerance_m: float


@dataclass
class Port:
    """A named geographic location."""
    name: str
    lat: float
    lon: float


@dataclass
class VoyageRequest:
    """Origin-destination pair with timing constraints."""
    voyage_id: str
    origin: Port
    destination: Port
    departure_time: datetime
    required_arrival_deadline: datetime


@dataclass
class PenaltyConfig:
    """Cost coefficients and emission factors loaded from penalties.yaml."""
    fuel_price_per_mt: float
    co2_cost_per_mt: float
    operational_hourly_rate: float
    delay_penalty_hourly: float
    storm_risk_multiplier: float
    co2_factor_vlsfo: float


@dataclass
class WeatherPoint:
    """A single weather observation / forecast grid point."""
    lat: float
    lon: float
    time: datetime
    wind_speed_kts: float
    wind_dir_deg: float
    wave_height_m: float
    current_speed_kts: float
    current_dir_deg: float


@dataclass
class Waypoint:
    """A point along the optimised route with computed metrics."""
    name: str
    lat: float
    lon: float
    time: datetime
    speed_knots: float
    fuel_burn_mt: float     # segment fuel burn
    co2_mt: float           # segment CO2
    segment_cost: float     # total segment cost (USD)


@dataclass
class RouteResult:
    """Complete output of the optimisation run."""
    voyage_id: str
    waypoints: List[Waypoint] = field(default_factory=list)
    total_fuel_mt: float = 0.0
    total_co2_mt: float = 0.0
    total_cost: float = 0.0
    total_distance_nm: float = 0.0
    total_duration_hours: float = 0.0

    def compute_totals(self) -> None:
        self.total_fuel_mt = sum(w.fuel_burn_mt for w in self.waypoints)
        self.total_co2_mt = sum(w.co2_mt for w in self.waypoints)
        self.total_cost = sum(w.segment_cost for w in self.waypoints)


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles between two points."""
    R_NM = 3440.065  # Earth radius in nautical miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R_NM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees from point 1 to point 2."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
