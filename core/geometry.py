"""
geometry.py
===========
Shape detection and dimension extraction from DXF entities.

Determines whether a column is circular or rectangular, extracts bounding
box dimensions (b × d) from polylines, detects rotation angles, and
parses dimension hints from layer names (e.g. 'BEAMS 25x80' → w=0.25, d=0.80).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════════════════

Point = tuple[float, float]


@dataclass
class ShapeInfo:
    """Detected shape from a DXF entity."""

    is_circular: bool = False
    width: float = 0.0  # b dimension (or diameter if circular)
    depth: float = 0.0  # d dimension
    diameter: float = 0.0  # only for circular
    center_x: float = 0.0
    center_y: float = 0.0
    angle: float = 0.0  # rotation in degrees


@dataclass
class DimensionHint:
    """Dimensions parsed from a layer name string."""

    dim1: Optional[float] = None  # first dimension (width or thickness)
    dim2: Optional[float] = None  # second dimension (depth)
    raw_match: str = ""  # the matched substring

    @property
    def has_two_dims(self) -> bool:
        return self.dim1 is not None and self.dim2 is not None

    @property
    def has_one_dim(self) -> bool:
        return self.dim1 is not None and self.dim2 is None


# ═══════════════════════════════════════════════════════════════════════════════
# Layer name dimension parser
# ═══════════════════════════════════════════════════════════════════════════════

# Pattern: matches "25x60", "25X60", "25x80", "300x600", etc.
_RE_TWO_DIMS = re.compile(r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)")

# Pattern: matches a standalone number after the element keyword
# e.g. "SLAB EDGE 300" → 300, "LINELOADS 15" → 15
_RE_SINGLE_DIM = re.compile(r"\b(\d+(?:\.\d+)?)\s*$")


def parse_dimensions_from_layer_name(layer_name: str) -> DimensionHint:
    """Extract dimension hints from a DXF layer name.

    Examples:
        'GC-BEAMS 25x80'      → DimensionHint(dim1=25, dim2=80)
        'GC-SLAB EDGE 300'    → DimensionHint(dim1=300)
        'GC-COLUMNS'          → DimensionHint()  (no dims found)
        'GC-PointLoad 50D'    → DimensionHint()  (50D not a pure number)
    """
    # Try two-dimensional pattern first
    m = _RE_TWO_DIMS.search(layer_name)
    if m:
        return DimensionHint(
            dim1=float(m.group(1)),
            dim2=float(m.group(2)),
            raw_match=m.group(0),
        )

    # Try single dimension — match trailing number
    # Strip everything before the last known keyword to avoid false matches
    m = _RE_SINGLE_DIM.search(layer_name)
    if m:
        val = float(m.group(1))
        # Sanity: ignore if the number looks like it could be a layer ID
        # (very small numbers in context of structural dims)
        if val >= 1.0:
            return DimensionHint(dim1=val, raw_match=m.group(0))

    return DimensionHint()


# ═══════════════════════════════════════════════════════════════════════════════
# Shape detection from DXF polygon vertices
# ═══════════════════════════════════════════════════════════════════════════════


def _distance(p1: Point, p2: Point) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def _centroid(pts: list[Point]) -> Point:
    n = len(pts)
    if n == 0:
        return (0.0, 0.0)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    return (cx, cy)


def detect_shape_from_polygon(pts: list[Point]) -> ShapeInfo:
    """Detect whether a closed polygon represents a rectangular or circular shape.

    - 4 vertices with ~90° corners → rectangular → extract b, d, angle
    - Many vertices forming a near-circle → circular → extract diameter
    - Otherwise → use bounding box as rectangular approximation
    """
    center = _centroid(pts)
    info = ShapeInfo(center_x=center[0], center_y=center[1])
    n = len(pts)

    if n < 3:
        return info

    # Check for near-circular: many points, all ~same distance from centroid
    if n >= 8:
        dists = [_distance(center, p) for p in pts]
        avg_r = sum(dists) / len(dists)
        if avg_r > 0:
            max_dev = max(abs(d - avg_r) / avg_r for d in dists)
            if max_dev < 0.1:  # within 10% of average radius → circular
                info.is_circular = True
                info.diameter = avg_r * 2
                info.width = info.diameter
                info.depth = info.diameter
                return info

    # Check for rectangle (4 vertices)
    if n == 4:
        # Compute side lengths
        sides = [_distance(pts[i], pts[(i + 1) % 4]) for i in range(4)]
        # Check perpendicularity via dot products
        dx1 = pts[1][0] - pts[0][0]
        dy1 = pts[1][1] - pts[0][1]
        dx2 = pts[2][0] - pts[1][0]
        dy2 = pts[2][1] - pts[1][1]
        dot = abs(dx1 * dx2 + dy1 * dy2)
        length1 = math.sqrt(dx1**2 + dy1**2)
        length2 = math.sqrt(dx2**2 + dy2**2)
        is_perp = dot < 0.05 * max(length1 * length2, 1e-9)

        if is_perp:
            # RAM column convention: b is the smaller side, d is the larger side.
            if sides[0] <= sides[1]:
                info.width = sides[0]
                info.depth = sides[1]
                info.angle = math.degrees(math.atan2(dy1, dx1))
            else:
                info.width = sides[1]
                info.depth = sides[0]
                info.angle = math.degrees(math.atan2(dy2, dx2))
            return info

    # Fallback: use bounding box
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    info.width = max(xs) - min(xs)
    info.depth = max(ys) - min(ys)
    return info


def detect_shape_from_circle(
    center_x: float, center_y: float, radius: float
) -> ShapeInfo:
    """Create ShapeInfo for a CIRCLE entity."""
    return ShapeInfo(
        is_circular=True,
        width=radius * 2,
        depth=radius * 2,
        diameter=radius * 2,
        center_x=center_x,
        center_y=center_y,
        angle=0.0,
    )


def bounding_box_dimensions(pts: list[Point]) -> tuple[float, float]:
    """Return (width, height) of the bounding box of a set of points."""
    if not pts:
        return (0.0, 0.0)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (max(xs) - min(xs), max(ys) - min(ys))
