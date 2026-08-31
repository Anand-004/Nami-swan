"""Output formatter: generates the strictly formatted CSV route file.

Enforces:
  - Coordinates to 4 decimal places
  - Date as DD/MM/YYYY
  - Time as HH:MM:55 (fixed seconds)
  - No duplicate consecutive waypoints
  - Waypoint intervals between 1 min and 3 hours
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import timedelta
from pathlib import Path
from typing import List

from .models import RouteResult, Waypoint

logger = logging.getLogger(__name__)

COLUMNS = [
    "waypoint_name",
    "latitude",
    "longitude",
    "date",
    "time",
    "speed_knots",
    "fuel_burn_mt",
    "co2_mt",
    "segment_cost",
]

MIN_INTERVAL = timedelta(minutes=1)
MAX_INTERVAL = timedelta(hours=3)


def _format_coord(value: float) -> str:
    """Format a coordinate to exactly 4 decimal places."""
    return f"{value:.4f}"


def _format_date(wp: Waypoint) -> str:
    """Format date as DD/MM/YYYY."""
    return wp.time.strftime("%d/%m/%Y")


def _format_time(wp: Waypoint) -> str:
    """Format time as HH:MM:55 (fixed seconds at :55 per spec)."""
    return wp.time.strftime("%H:%M") + ":55"


def _is_duplicate(a: Waypoint, b: Waypoint) -> bool:
    """Check if two consecutive waypoints have identical coordinates."""
    return (
        round(a.lat, 4) == round(b.lat, 4)
        and round(a.lon, 4) == round(b.lon, 4)
    )


def _interpolate_waypoints(waypoints: List[Waypoint]) -> List[Waypoint]:
    """Insert intermediate waypoints where the interval exceeds 3 hours,
    and remove duplicates. Also ensures minimum 1-minute spacing."""
    if not waypoints:
        return waypoints

    result: List[Waypoint] = [waypoints[0]]

    for i in range(1, len(waypoints)):
        prev = result[-1]
        curr = waypoints[i]

        # Skip duplicates
        if _is_duplicate(prev, curr):
            logger.debug("Removing duplicate waypoint at (%.4f, %.4f)", curr.lat, curr.lon)
            continue

        # Check interval
        delta = curr.time - prev.time
        if delta < timedelta(0):
            delta = timedelta(minutes=5)  # safety

        if delta > MAX_INTERVAL:
            # Insert intermediate points
            n_inserts = int(delta / MAX_INTERVAL)
            for j in range(1, n_inserts + 1):
                frac = j / (n_inserts + 1)
                interp_lat = prev.lat + frac * (curr.lat - prev.lat)
                interp_lon = prev.lon + frac * (curr.lon - prev.lon)
                interp_time = prev.time + timedelta(
                    seconds=delta.total_seconds() * frac
                )
                interp_wp = Waypoint(
                    name=f"{prev.name}_I{j}",
                    lat=round(interp_lat, 4),
                    lon=round(interp_lon, 4),
                    time=interp_time,
                    speed_knots=curr.speed_knots,
                    fuel_burn_mt=curr.fuel_burn_mt / (n_inserts + 1),
                    co2_mt=curr.co2_mt / (n_inserts + 1),
                    segment_cost=curr.segment_cost / (n_inserts + 1),
                )
                result.append(interp_wp)

            # Adjust remaining portion of the original waypoint
            curr_adjusted = Waypoint(
                name=curr.name,
                lat=curr.lat,
                lon=curr.lon,
                time=curr.time,
                speed_knots=curr.speed_knots,
                fuel_burn_mt=curr.fuel_burn_mt / (n_inserts + 1),
                co2_mt=curr.co2_mt / (n_inserts + 1),
                segment_cost=curr.segment_cost / (n_inserts + 1),
            )
            result.append(curr_adjusted)
        elif delta < MIN_INTERVAL and i > 1:
            # Too close — skip unless it's the final waypoint
            if i < len(waypoints) - 1:
                logger.debug(
                    "Skipping waypoint too close (%s interval) at (%.4f, %.4f)",
                    delta, curr.lat, curr.lon,
                )
                continue
            else:
                result.append(curr)
        else:
            result.append(curr)

    return result


def format_route_csv(route: RouteResult, output_path: Path) -> Path:
    """Write the route to a CSV file with strict formatting.

    Returns the path of the written file.
    """
    waypoints = _interpolate_waypoints(route.waypoints)

    logger.info("Writing %d waypoints to %s", len(waypoints), output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)

        for wp in waypoints:
            writer.writerow([
                wp.name,
                _format_coord(wp.lat),
                _format_coord(wp.lon),
                _format_date(wp),
                _format_time(wp),
                f"{wp.speed_knots:.2f}",
                f"{wp.fuel_burn_mt:.4f}",
                f"{wp.co2_mt:.4f}",
                f"{wp.segment_cost:.2f}",
            ])

    logger.info("Route CSV written successfully")
    return output_path


def format_route_string(route: RouteResult) -> str:
    """Return the formatted CSV as a string (for testing / stdout)."""
    waypoints = _interpolate_waypoints(route.waypoints)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(COLUMNS)
    for wp in waypoints:
        writer.writerow([
            wp.name,
            _format_coord(wp.lat),
            _format_coord(wp.lon),
            _format_date(wp),
            _format_time(wp),
            f"{wp.speed_knots:.2f}",
            f"{wp.fuel_burn_mt:.4f}",
            f"{wp.co2_mt:.4f}",
            f"{wp.segment_cost:.2f}",
        ])
    return buf.getvalue()
