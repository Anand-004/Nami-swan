"""Tests for output_formatter module."""

import csv
import io
import re
from datetime import datetime, timezone

import pytest

from src.models import RouteResult, Waypoint
from src.output_formatter import (
    COLUMNS,
    _format_coord,
    _format_date,
    _format_time,
    _is_duplicate,
    _interpolate_waypoints,
    format_route_string,
)


def _make_waypoint(name, lat, lon, time, speed=12.0, fuel=0.5, co2=0.2, cost=100.0):
    return Waypoint(name=name, lat=lat, lon=lon, time=time,
                    speed_knots=speed, fuel_burn_mt=fuel, co2_mt=co2, segment_cost=cost)


class TestFormatCoord:
    def test_four_decimals(self):
        assert _format_coord(1.2) == "1.2000"
        assert _format_coord(12.3456) == "12.3456"
        assert _format_coord(-5.12345) == "-5.1235"  # rounds

    def test_large_coordinate(self):
        result = _format_coord(103.8519)
        assert result == "103.8519"


class TestFormatDate:
    def test_dd_mm_yyyy(self):
        wp = _make_waypoint("W", 0, 0, datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc))
        assert _format_date(wp) == "01/09/2026"

    def test_single_digit_day(self):
        wp = _make_waypoint("W", 0, 0, datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc))
        assert _format_date(wp) == "05/01/2026"


class TestFormatTime:
    def test_fixed_seconds(self):
        wp = _make_waypoint("W", 0, 0, datetime(2026, 9, 1, 14, 30, tzinfo=timezone.utc))
        result = _format_time(wp)
        assert result == "14:30:55"
        assert result.endswith(":55")

    def test_midnight(self):
        wp = _make_waypoint("W", 0, 0, datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc))
        assert _format_time(wp) == "00:00:55"


class TestDuplicateDetection:
    def test_same_coords_duplicate(self):
        a = _make_waypoint("A", 1.2345, 2.3456, datetime.now(timezone.utc))
        b = _make_waypoint("B", 1.2345, 2.3456, datetime.now(timezone.utc))
        assert _is_duplicate(a, b) is True

    def test_different_coords_not_duplicate(self):
        a = _make_waypoint("A", 1.2345, 2.3456, datetime.now(timezone.utc))
        b = _make_waypoint("B", 1.2346, 2.3456, datetime.now(timezone.utc))
        assert _is_duplicate(a, b) is False


class TestCSVOutput:
    def test_header_columns(self):
        route = RouteResult(voyage_id="TEST")
        route.waypoints = [
            _make_waypoint("WP000", 1.2902, 103.8519, datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc), speed=0.0, fuel=0.0, co2=0.0, cost=0.0),
            _make_waypoint("WP001", 2.0000, 100.0000, datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)),
        ]
        csv_str = format_route_string(route)
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert header == COLUMNS

    def test_coordinate_precision(self):
        route = RouteResult(voyage_id="TEST")
        route.waypoints = [
            _make_waypoint("WP000", 1.2, 103.8, datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc)),
            _make_waypoint("WP001", 2.5, 100.5, datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)),
        ]
        csv_str = format_route_string(route)
        lines = csv_str.strip().split("\n")
        row = lines[1].split(",")
        lat_str = row[1]
        lon_str = row[2]
        # Must have at least 4 decimal places
        assert re.match(r"-?\d+\.\d{4,}", lat_str)
        assert re.match(r"-?\d+\.\d{4,}", lon_str)

    def test_time_ends_with_55(self):
        route = RouteResult(voyage_id="TEST")
        route.waypoints = [
            _make_waypoint("WP000", 1.0, 103.0, datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc)),
            _make_waypoint("WP001", 2.0, 100.0, datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)),
        ]
        csv_str = format_route_string(route)
        lines = csv_str.strip().split("\n")
        for line in lines[1:]:
            time_val = line.split(",")[4]
            assert time_val.endswith(":55"), f"Time {time_val} should end with :55"

    def test_no_duplicate_consecutive_waypoints(self):
        route = RouteResult(voyage_id="TEST")
        t = datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc)
        route.waypoints = [
            _make_waypoint("WP000", 1.0, 100.0, t),
            _make_waypoint("WP001", 1.0, 100.0, t),  # duplicate
            _make_waypoint("WP002", 2.0, 99.0, datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)),
        ]
        csv_str = format_route_string(route)
        lines = csv_str.strip().split("\n")
        coords = [(l.split(",")[1], l.split(",")[2]) for l in lines[1:]]
        for i in range(1, len(coords)):
            assert coords[i] != coords[i - 1], "Consecutive duplicate found"
