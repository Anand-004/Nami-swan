"""Grid builder: creates a spatial oceanic navigation grid and performs
polygon intersection checks against land/restricted zones."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set, Tuple

import numpy as np
from shapely.geometry import LineString, Point, Polygon, shape

from .models import Port

logger = logging.getLogger(__name__)

# Type aliases
Coord = Tuple[float, float]  # (lat, lon)


def _build_zone_polygons(geojson: Dict[str, Any]) -> List[Polygon]:
    """Convert GeoJSON feature collection into Shapely Polygon objects."""
    polygons: List[Polygon] = []
    for feature in geojson.get("features", []):
        geom = shape(feature["geometry"])
        polygons.append(geom)
    return polygons


def _is_in_restricted_zone(lat: float, lon: float, zones: List[Polygon]) -> bool:
    """Check whether a single point falls inside any restricted polygon.

    Note: GeoJSON uses (lon, lat) ordering for coordinates.
    """
    pt = Point(lon, lat)
    return any(zone.contains(pt) for zone in zones)


def _segment_crosses_zone(
    lat1: float, lon1: float, lat2: float, lon2: float, zones: List[Polygon]
) -> bool:
    """Return True if the great-circle segment (approximated as a line)
    intersects any restricted polygon."""
    line = LineString([(lon1, lat1), (lon2, lat2)])
    return any(zone.intersects(line) for zone in zones)


class OceanGrid:
    """A regular lat/lon grid over the ocean, pruned of restricted zones.

    Attributes:
        resolution: grid spacing in degrees.
        nodes: set of (lat, lon) tuples representing navigable ocean cells.
        zones: list of Shapely polygons for restricted areas.
    """

    def __init__(
        self,
        origin: Port,
        destination: Port,
        geojson: Dict[str, Any],
        resolution: float = 0.5,
        padding_deg: float = 2.0,
    ) -> None:
        self.resolution = resolution
        self.zones = _build_zone_polygons(geojson)

        # Bounding box with padding
        lat_min = min(origin.lat, destination.lat) - padding_deg
        lat_max = max(origin.lat, destination.lat) + padding_deg
        lon_min = min(origin.lon, destination.lon) - padding_deg
        lon_max = max(origin.lon, destination.lon) + padding_deg

        # Build navigable node set
        self.nodes: Set[Coord] = set()
        lat = lat_min
        while lat <= lat_max:
            lon = lon_min
            while lon <= lon_max:
                r_lat = round(lat, 4)
                r_lon = round(lon, 4)
                if not _is_in_restricted_zone(r_lat, r_lon, self.zones):
                    self.nodes.add((r_lat, r_lon))
                lon += resolution
            lat += resolution

        # Always include exact origin/destination if navigable
        for port in (origin, destination):
            coord = (round(port.lat, 4), round(port.lon, 4))
            if not _is_in_restricted_zone(coord[0], coord[1], self.zones):
                self.nodes.add(coord)

        logger.info(
            "Ocean grid: %d navigable nodes (%.1f° res, bbox %.1f–%.1f lat, %.1f–%.1f lon)",
            len(self.nodes), resolution, lat_min, lat_max, lon_min, lon_max,
        )

    def neighbors(self, node: Coord) -> List[Coord]:
        """Return navigable neighbors of a grid node (8-connected + port snapping).

        Neighbors within ~1.5x grid resolution are considered reachable in one step.
        """
        lat, lon = node
        res = self.resolution
        candidates: List[Coord] = []
        for dlat in (-res, 0, res):
            for dlon in (-res, 0, res):
                if dlat == 0 and dlon == 0:
                    continue
                nb = (round(lat + dlat, 4), round(lon + dlon, 4))
                if nb in self.nodes:
                    candidates.append(nb)
        return candidates

    def is_segment_clear(self, n1: Coord, n2: Coord) -> bool:
        """Check that a direct segment between two nodes does not cross
        any restricted zone."""
        return not _segment_crosses_zone(n1[0], n1[1], n2[0], n2[1], self.zones)

    def snap_to_grid(self, lat: float, lon: float) -> Coord:
        """Snap an arbitrary coordinate to the nearest navigable grid node."""
        best: Coord = min(
            self.nodes,
            key=lambda n: (n[0] - lat) ** 2 + (n[1] - lon) ** 2,
        )
        return best
