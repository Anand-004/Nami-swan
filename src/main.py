"""CLI entry point: orchestrates the full voyage optimisation pipeline.

Usage:
    python -m src.main --config config/penalties.yaml --voyage data/inputs/voyage_request.json
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .data_loader import (
    load_penalties,
    load_restricted_zones,
    load_vessel_specs,
    load_voyage_request,
    load_weather_forecast,
)
from .grid_builder import OceanGrid
from .optimizer import find_optimal_route
from .output_formatter import format_route_csv


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nami",
        description="Nami-swan: Ship Voyage Route Optimization Engine",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/penalties.yaml"),
        help="Path to penalties/cost YAML config (default: config/penalties.yaml)",
    )
    parser.add_argument(
        "--vessel",
        type=Path,
        default=Path("config/vessel_specs.json"),
        help="Path to vessel specs JSON (default: config/vessel_specs.json)",
    )
    parser.add_argument(
        "--voyage",
        type=Path,
        required=True,
        help="Path to voyage request JSON",
    )
    parser.add_argument(
        "--zones",
        type=Path,
        default=Path("data/static/restricted_zones.geojson"),
        help="Path to restricted zones GeoJSON",
    )
    parser.add_argument(
        "--weather",
        type=Path,
        default=Path("data/weather/sample_forecast.json"),
        help="Path to weather forecast JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/outputs/optimized_route.csv"),
        help="Output CSV path (default: data/outputs/optimized_route.csv)",
    )
    parser.add_argument(
        "--grid-resolution",
        type=float,
        default=0.5,
        help="Ocean grid resolution in degrees (default: 0.5)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    logger = logging.getLogger("nami")

    logger.info("=" * 60)
    logger.info("  Nami-swan: Ship Voyage Route Optimization Engine")
    logger.info("=" * 60)

    # 1. Load all data
    logger.info("Loading configuration and data...")
    penalties = load_penalties(args.config)
    vessel = load_vessel_specs(args.vessel)
    voyage = load_voyage_request(args.voyage)
    zones_geojson = load_restricted_zones(args.zones)
    weather_points = load_weather_forecast(args.weather)

    logger.info("Vessel: %s (%s)", vessel.vessel_id, vessel.vessel_type)
    logger.info("Voyage: %s -> %s", voyage.origin.name, voyage.destination.name)
    logger.info("Departure: %s", voyage.departure_time)
    logger.info("Deadline:  %s", voyage.required_arrival_deadline)
    logger.info("Weather points loaded: %d", len(weather_points))

    # 2. Build ocean grid
    logger.info("Building ocean navigation grid (%.2f° resolution)...", args.grid_resolution)
    t0 = time.perf_counter()
    grid = OceanGrid(
        origin=voyage.origin,
        destination=voyage.destination,
        geojson=zones_geojson,
        resolution=args.grid_resolution,
    )
    logger.info("Grid built in %.2fs — %d navigable nodes", time.perf_counter() - t0, len(grid.nodes))

    # 3. Run optimisation
    logger.info("Running A* route optimisation...")
    t0 = time.perf_counter()
    route = find_optimal_route(
        grid=grid,
        voyage=voyage,
        vessel=vessel,
        penalties=penalties,
        weather_points=weather_points,
    )
    elapsed = time.perf_counter() - t0
    logger.info("Optimisation completed in %.2fs", elapsed)

    # 4. Write output
    output_path = format_route_csv(route, args.output)

    # 5. Summary
    logger.info("-" * 60)
    logger.info("VOYAGE SUMMARY")
    logger.info("-" * 60)
    logger.info("  Waypoints:      %d", len(route.waypoints))
    logger.info("  Total fuel:     %.2f MT", route.total_fuel_mt)
    logger.info("  Total CO2:      %.2f MT", route.total_co2_mt)
    logger.info("  Total cost:     $%.2f", route.total_cost)
    if route.waypoints:
        first = route.waypoints[0]
        last = route.waypoints[-1]
        duration = (last.time - first.time).total_seconds() / 3600
        logger.info("  Duration:       %.1f hours", duration)
        on_time = last.time <= voyage.required_arrival_deadline
        logger.info("  On-time:        %s", "YES ✓" if on_time else "NO ✗")
    logger.info("  Output:         %s", output_path)
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
