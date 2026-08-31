"""Optimizer: Weighted A* pathfinding over a dynamic spatio-temporal ocean grid."""

from __future__ import annotations

import heapq
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .cost_engine import compute_segment_cost
from .grid_builder import OceanGrid
from .models import (
    PenaltyConfig,
    Port,
    RouteResult,
    VesselSpec,
    VoyageRequest,
    Waypoint,
    WeatherPoint,
    haversine_nm,
)

logger = logging.getLogger(__name__)

Coord = Tuple[float, float]


class WeatherIndex:
    """Spatial index for fast nearest-weather-point lookup."""

    def __init__(self, points: List[WeatherPoint]) -> None:
        self.points = points

    def nearest(self, lat: float, lon: float, time: datetime) -> Optional[WeatherPoint]:
        """Return the weather point closest in space (and roughly in time)."""
        if not self.points:
            return None
        best: Optional[WeatherPoint] = None
        best_score = float("inf")
        for wp in self.points:
            dist_sq = (wp.lat - lat) ** 2 + (wp.lon - lon) ** 2
            time_diff_h = abs((wp.time - time).total_seconds()) / 3600.0
            score = dist_sq + (time_diff_h * 0.1) ** 2  # space-weighted
            if score < best_score:
                best_score = score
                best = wp
        return best


def _heuristic(node: Coord, goal: Coord, vessel: VesselSpec, penalties: PenaltyConfig) -> float:
    """Admissible A* heuristic: minimum possible cost to reach goal.

    Uses straight-line distance at max speed with only operational cost.
    """
    dist = haversine_nm(node[0], node[1], goal[0], goal[1])
    if dist < 0.01:
        return 0.0
    hours = dist / vessel.max_speed_knots
    # Minimum fuel at max speed
    fuel_rate = (vessel.base_fuel_rate_mt_day / 24.0) * (
        vessel.max_speed_knots / vessel.design_speed_knots
    ) ** 3
    fuel = fuel_rate * hours
    co2 = fuel * penalties.co2_factor_vlsfo
    return (
        fuel * penalties.fuel_price_per_mt
        + co2 * penalties.co2_cost_per_mt
        + hours * penalties.operational_hourly_rate
    ) * 0.8  # stay admissible with 0.8 factor


def find_optimal_route(
    grid: OceanGrid,
    voyage: VoyageRequest,
    vessel: VesselSpec,
    penalties: PenaltyConfig,
    weather_points: List[WeatherPoint],
    w_heuristic: float = 1.2,
) -> RouteResult:
    """Run weighted A* to find the lowest-cost route from origin to destination.

    Args:
        grid: navigable ocean grid
        voyage: voyage request with origin/destination/schedule
        vessel: vessel mechanical specs
        penalties: cost configuration
        weather_points: forecast weather data
        w_heuristic: heuristic weight (1.0 = standard A*, >1.0 = greedy bias)

    Returns:
        RouteResult with ordered waypoints and aggregate metrics.
    """
    weather_idx = WeatherIndex(weather_points)

    start = grid.snap_to_grid(voyage.origin.lat, voyage.origin.lon)
    goal = grid.snap_to_grid(voyage.destination.lat, voyage.destination.lon)

    logger.info("A* search: %s -> %s", start, goal)
    logger.info("Start time: %s  Deadline: %s", voyage.departure_time, voyage.required_arrival_deadline)

    # Priority queue: (f_score, counter, node)
    counter = 0
    open_set: List[Tuple[float, int, Coord]] = []
    heapq.heappush(open_set, (0.0, counter, start))

    g_score: Dict[Coord, float] = {start: 0.0}
    came_from: Dict[Coord, Coord] = {}
    node_time: Dict[Coord, datetime] = {start: voyage.departure_time}
    node_data: Dict[Coord, dict] = {}  # segment metrics for each node

    visited = 0
    max_iterations = 500_000

    while open_set and visited < max_iterations:
        _, _, current = heapq.heappop(open_set)
        visited += 1

        if visited % 5000 == 0:
            logger.debug("A* visited %d nodes, queue size %d", visited, len(open_set))

        if current == goal:
            logger.info("A* found goal after visiting %d nodes", visited)
            break

        current_time = node_time[current]

        for neighbor in grid.neighbors(current):
            # Check segment doesn't cross restricted zones
            if not grid.is_segment_clear(current, neighbor):
                continue

            # Get weather at midpoint of segment
            mid_lat = (current[0] + neighbor[0]) / 2
            mid_lon = (current[1] + neighbor[1]) / 2
            weather = weather_idx.nearest(mid_lat, mid_lon, current_time)

            # Remaining distance heuristic for speed planning
            remaining_nm = haversine_nm(neighbor[0], neighbor[1], goal[0], goal[1])

            seg = compute_segment_cost(
                current[0], current[1],
                neighbor[0], neighbor[1],
                current_time,
                voyage.required_arrival_deadline,
                vessel,
                penalties,
                weather,
                remaining_nm,
            )

            tentative_g = g_score[current] + seg["total_cost"]

            if tentative_g < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current
                node_time[neighbor] = seg["arrival_time"]
                node_data[neighbor] = seg

                h = _heuristic(neighbor, goal, vessel, penalties)
                f = tentative_g + w_heuristic * h
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor))

    # Reconstruct path
    if goal not in came_from and start != goal:
        logger.warning("A* could not find a path to the destination!")
        # Return a direct route as fallback
        return _direct_route(voyage, vessel, penalties, weather_idx)

    path: List[Coord] = []
    node = goal
    while node in came_from:
        path.append(node)
        node = came_from[node]
    path.append(start)
    path.reverse()

    logger.info("Route found: %d waypoints", len(path))

    # Build waypoint list
    result = RouteResult(voyage_id=voyage.voyage_id)
    current_time = voyage.departure_time

    for i, coord in enumerate(path):
        if i == 0:
            wp = Waypoint(
                name=f"WP{i:03d}_DEPART",
                lat=coord[0],
                lon=coord[1],
                time=current_time,
                speed_knots=0.0,
                fuel_burn_mt=0.0,
                co2_mt=0.0,
                segment_cost=0.0,
            )
        else:
            seg = node_data.get(coord, {})
            current_time = node_time.get(coord, current_time)
            wp = Waypoint(
                name=f"WP{i:03d}",
                lat=coord[0],
                lon=coord[1],
                time=current_time,
                speed_knots=seg.get("speed_kts", vessel.design_speed_knots),
                fuel_burn_mt=seg.get("fuel_mt", 0.0),
                co2_mt=seg.get("co2_mt", 0.0),
                segment_cost=seg.get("total_cost", 0.0),
            )
        result.waypoints.append(wp)

    # Label last waypoint as arrival
    if result.waypoints:
        result.waypoints[-1].name = f"WP{len(path)-1:03d}_ARRIVE"

    result.compute_totals()
    return result


def _direct_route(
    voyage: VoyageRequest,
    vessel: VesselSpec,
    penalties: PenaltyConfig,
    weather_idx: WeatherIndex,
) -> RouteResult:
    """Fallback: generate a direct great-circle route when A* cannot find a path."""
    logger.warning("Generating direct fallback route")

    origin = voyage.origin
    dest = voyage.destination
    total_nm = haversine_nm(origin.lat, origin.lon, dest.lat, dest.lon)

    # Generate intermediate waypoints every ~50 nm
    n_segments = max(int(total_nm / 50), 2)
    result = RouteResult(voyage_id=voyage.voyage_id)
    current_time = voyage.departure_time

    for i in range(n_segments + 1):
        frac = i / n_segments
        lat = origin.lat + frac * (dest.lat - origin.lat)
        lon = origin.lon + frac * (dest.lon - origin.lon)

        if i == 0:
            wp = Waypoint(
                name="WP000_DEPART", lat=round(lat, 4), lon=round(lon, 4),
                time=current_time, speed_knots=0.0,
                fuel_burn_mt=0.0, co2_mt=0.0, segment_cost=0.0,
            )
        else:
            prev = result.waypoints[-1]
            seg_dist = haversine_nm(prev.lat, prev.lon, lat, lon)
            remaining = haversine_nm(lat, lon, dest.lat, dest.lon)
            weather = weather_idx.nearest(lat, lon, current_time)

            seg = compute_segment_cost(
                prev.lat, prev.lon, lat, lon,
                current_time, voyage.required_arrival_deadline,
                vessel, penalties, weather, remaining,
            )
            current_time = seg["arrival_time"]
            name = f"WP{i:03d}_ARRIVE" if i == n_segments else f"WP{i:03d}"
            wp = Waypoint(
                name=name, lat=round(lat, 4), lon=round(lon, 4),
                time=current_time, speed_knots=seg["speed_kts"],
                fuel_burn_mt=seg["fuel_mt"], co2_mt=seg["co2_mt"],
                segment_cost=seg["total_cost"],
            )
        result.waypoints.append(wp)

    result.compute_totals()
    return result
