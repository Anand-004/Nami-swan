"""Data loader: ingestion for JSON, YAML, and GeoJSON configuration files."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .models import PenaltyConfig, Port, VesselSpec, VoyageRequest, WeatherPoint


def _parse_iso(s: str) -> datetime:
    """Parse ISO-8601 datetime string (with or without 'Z' suffix)."""
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def load_penalties(path: Path) -> PenaltyConfig:
    """Load cost / emission config from a YAML file."""
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    costs = raw["costs"]
    emissions = raw["emissions"]
    return PenaltyConfig(
        fuel_price_per_mt=costs["fuel_price_per_mt"],
        co2_cost_per_mt=costs["co2_cost_per_mt"],
        operational_hourly_rate=costs["operational_hourly_rate"],
        delay_penalty_hourly=costs["delay_penalty_hourly"],
        storm_risk_multiplier=costs["storm_risk_multiplier"],
        co2_factor_vlsfo=emissions["co2_factor_vlsfo"],
    )


def load_vessel_specs(path: Path) -> VesselSpec:
    """Load vessel mechanical specs from a JSON file."""
    with open(path, "r") as f:
        raw = json.load(f)
    return VesselSpec(**raw)


def load_voyage_request(path: Path) -> VoyageRequest:
    """Load voyage request (origin, destination, schedule) from JSON."""
    with open(path, "r") as f:
        raw = json.load(f)
    return VoyageRequest(
        voyage_id=raw["voyage_id"],
        origin=Port(**raw["origin"]),
        destination=Port(**raw["destination"]),
        departure_time=_parse_iso(raw["departure_time"]),
        required_arrival_deadline=_parse_iso(raw["required_arrival_deadline"]),
    )


def load_restricted_zones(path: Path) -> Dict[str, Any]:
    """Load GeoJSON restricted zone polygons.

    Returns the raw GeoJSON dict — grid_builder converts to Shapely geometries.
    """
    with open(path, "r") as f:
        return json.load(f)


def load_weather_forecast(path: Path) -> List[WeatherPoint]:
    """Load weather forecast grid points from JSON."""
    with open(path, "r") as f:
        raw = json.load(f)
    points: List[WeatherPoint] = []
    for p in raw["grid_points"]:
        points.append(WeatherPoint(
            lat=p["lat"],
            lon=p["lon"],
            time=_parse_iso(p["time"]),
            wind_speed_kts=p["wind_speed_kts"],
            wind_dir_deg=p["wind_dir_deg"],
            wave_height_m=p["wave_height_m"],
            current_speed_kts=p["current_speed_kts"],
            current_dir_deg=p["current_dir_deg"],
        ))
    return points
