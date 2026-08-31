"""Tests for physics_engine module."""

import math
import pytest

from src.models import VesselSpec
from src.physics_engine import (
    compute_fuel_burn,
    compute_co2,
    compute_speed_over_ground,
    optimal_speed_for_segment,
    _wind_resistance_factor,
    _wave_resistance_factor,
)


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


class TestSpeedOverGround:
    def test_no_current(self):
        sog = compute_speed_over_ground(14.0, 90.0, 0.0, 0.0)
        assert sog == pytest.approx(14.0, abs=0.1)

    def test_following_current(self):
        sog = compute_speed_over_ground(14.0, 90.0, 2.0, 90.0)
        assert sog > 14.0, "Following current should increase SOG"

    def test_opposing_current(self):
        sog = compute_speed_over_ground(14.0, 90.0, 2.0, 270.0)
        assert sog < 14.0, "Opposing current should decrease SOG"

    def test_sog_never_negative(self):
        sog = compute_speed_over_ground(5.0, 0.0, 10.0, 180.0)
        assert sog >= 0.5


class TestFuelBurn:
    def test_zero_distance(self, vessel):
        fuel = compute_fuel_burn(vessel, 0.0, 14.0)
        assert fuel == 0.0

    def test_design_speed_fuel(self, vessel):
        fuel = compute_fuel_burn(vessel, 140.0, 14.0)
        expected_hours = 140.0 / 14.0
        expected_rate = vessel.base_fuel_rate_mt_day / 24.0
        assert fuel == pytest.approx(expected_rate * expected_hours, rel=0.05)

    def test_higher_speed_more_fuel(self, vessel):
        fuel_design = compute_fuel_burn(vessel, 100.0, 14.0)
        fuel_max = compute_fuel_burn(vessel, 100.0, 16.5)
        assert fuel_max > fuel_design, "Higher speed should burn more fuel"

    def test_lower_speed_less_fuel(self, vessel):
        fuel_design = compute_fuel_burn(vessel, 100.0, 14.0)
        fuel_slow = compute_fuel_burn(vessel, 100.0, 10.0)
        assert fuel_slow < fuel_design, "Lower speed should burn less fuel"


class TestCO2:
    def test_co2_calculation(self):
        co2 = compute_co2(10.0, 3.114)
        assert co2 == pytest.approx(31.14, rel=0.01)

    def test_zero_fuel_zero_co2(self):
        assert compute_co2(0.0, 3.114) == 0.0


class TestWindResistance:
    def test_calm(self):
        assert _wind_resistance_factor(0.0, 0.0, 0.0) == pytest.approx(1.0, abs=0.01)

    def test_headwind_increases(self):
        factor = _wind_resistance_factor(20.0, 0.0, 0.0)
        assert factor > 1.0

    def test_tailwind_decreases(self):
        factor = _wind_resistance_factor(20.0, 180.0, 0.0)
        assert factor < 1.0


class TestWaveResistance:
    def test_calm_seas(self):
        assert _wave_resistance_factor(0.0) == 1.0

    def test_moderate_waves(self):
        factor = _wave_resistance_factor(2.0)
        assert factor > 1.0

    def test_heavy_seas(self):
        factor = _wave_resistance_factor(5.0)
        assert factor > _wave_resistance_factor(2.0)


class TestOptimalSpeed:
    def test_plenty_of_time(self, vessel):
        speed = optimal_speed_for_segment(vessel, 100.0, 20.0)
        assert vessel.min_speed_knots <= speed <= vessel.max_speed_knots

    def test_tight_deadline(self, vessel):
        speed = optimal_speed_for_segment(vessel, 100.0, 5.0)
        assert speed >= vessel.min_speed_knots

    def test_no_time_left(self, vessel):
        speed = optimal_speed_for_segment(vessel, 100.0, 0.0)
        assert speed == vessel.max_speed_knots
