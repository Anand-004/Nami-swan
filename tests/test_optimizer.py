"""Tests for optimizer module."""

import pytest
from datetime import datetime, timezone

from src.models import PenaltyConfig, Port, VesselSpec, VoyageRequest, haversine_nm
from src.grid_builder import OceanGrid
from src.optimizer import find_optimal_route, WeatherIndex


@pytest.fixture
def vessel():
    return VesselSpec(
        vessel_id="TEST-001",
        vessel_type="Test Carrier",
        design_speed_knots=14.0,
        min_speed_knots=8.0,
        max_speed_knots=16.5,
        rpm_min=65,
        rpm_max=105,
        fuel_type="VLSFO",
        base_fuel_rate_mt_day=24.5,
        max_wave_height_tolerance_m=4.5,
    )


@pytest.fixture
def penalties():
    return PenaltyConfig(
        fuel_price_per_mt=650.0,
        co2_cost_per_mt=90.0,
        operational_hourly_rate=450.0,
        delay_penalty_hourly=1200.0,
        storm_risk_multiplier=2.5,
        co2_factor_vlsfo=3.114,
    )


@pytest.fixture
def simple_voyage():
    return VoyageRequest(
        voyage_id="TEST-VOY",
        origin=Port("Origin", 2.0, 88.0),
        destination=Port("Dest", 4.0, 84.0),
        departure_time=datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc),
        required_arrival_deadline=datetime(2026, 9, 5, 18, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def simple_geojson():
    """Minimal restricted zone that won't block the test route."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Test Land", "zone_type": "land"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[70.0, 0.0], [72.0, 0.0], [72.0, 2.0], [70.0, 2.0], [70.0, 0.0]]],
                },
            }
        ],
    }


class TestHaversine:
    def test_zero_distance(self):
        assert haversine_nm(10.0, 20.0, 10.0, 20.0) == 0.0

    def test_known_distance(self):
        # Singapore to Colombo ~1450 nm
        dist = haversine_nm(1.29, 103.85, 6.93, 79.86)
        assert 1400 < dist < 1600

    def test_symmetry(self):
        d1 = haversine_nm(0.0, 0.0, 10.0, 10.0)
        d2 = haversine_nm(10.0, 10.0, 0.0, 0.0)
        assert d1 == pytest.approx(d2, rel=1e-6)


class TestWeatherIndex:
    def test_empty_points(self):
        idx = WeatherIndex([])
        assert idx.nearest(0, 0, datetime.now()) is None


class TestFindOptimalRoute:
    def test_route_has_waypoints(self, simple_voyage, vessel, penalties, simple_geojson):
        grid = OceanGrid(
            simple_voyage.origin, simple_voyage.destination,
            simple_geojson, resolution=1.0,
        )
        route = find_optimal_route(grid, simple_voyage, vessel, penalties, [])
        assert len(route.waypoints) >= 2, "Route must have at least origin and destination"

    def test_route_starts_near_origin(self, simple_voyage, vessel, penalties, simple_geojson):
        grid = OceanGrid(
            simple_voyage.origin, simple_voyage.destination,
            simple_geojson, resolution=1.0,
        )
        route = find_optimal_route(grid, simple_voyage, vessel, penalties, [])
        first = route.waypoints[0]
        dist = haversine_nm(first.lat, first.lon, simple_voyage.origin.lat, simple_voyage.origin.lon)
        assert dist < 100, f"First waypoint too far from origin: {dist} nm"

    def test_route_ends_near_destination(self, simple_voyage, vessel, penalties, simple_geojson):
        grid = OceanGrid(
            simple_voyage.origin, simple_voyage.destination,
            simple_geojson, resolution=1.0,
        )
        route = find_optimal_route(grid, simple_voyage, vessel, penalties, [])
        last = route.waypoints[-1]
        dist = haversine_nm(last.lat, last.lon, simple_voyage.destination.lat, simple_voyage.destination.lon)
        assert dist < 100, f"Last waypoint too far from dest: {dist} nm"

    def test_total_cost_positive(self, simple_voyage, vessel, penalties, simple_geojson):
        grid = OceanGrid(
            simple_voyage.origin, simple_voyage.destination,
            simple_geojson, resolution=1.0,
        )
        route = find_optimal_route(grid, simple_voyage, vessel, penalties, [])
        assert route.total_cost > 0
