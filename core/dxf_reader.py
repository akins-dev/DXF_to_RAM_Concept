"""
dxf_reader.py
=============
Reads a DXF file and extracts geometry for every structural element and load
type, with automatic shape detection for columns.

Outputs per element role
------------------------
  walls        → list of Segment  ((x0,y0),(x1,y1))
  columns      → list of ColumnGeom (center, shape info, rotation)
  slabs        → list of Polygon  [(x,y), ...]
  beams        → list of Segment
  openings     → list of Polygon
  drop_caps    → list of Polygon
  drop_panels  → list of Polygon
  point_supports → list of (x, y)
  line_supports  → list of Segment
  area_springs   → list of Polygon
  line_loads   → list of Segment
  area_loads   → list of Polygon
  point_loads  → list of (x, y)

All coordinates are converted to metres during extraction via unit_scale.

Supported entity types per role
-------------------------------
  Linear (wall / beam / line_support / lineload):
    LINE, LWPOLYLINE, POLYLINE (2-D)
  Polygon (slab / opening / drop_cap / drop_panel / area_spring / areaload):
    LWPOLYLINE (closed), POLYLINE (closed), HATCH, SPLINE, SOLID, 3DFACE
  Point (point_support / pointload):
    POINT, CIRCLE (centre)
  Column:
    CIRCLE → circular column (centre + radius)
    LWPOLYLINE (closed) → detect shape from vertices
    POLYLINE (closed, 2D) → detect shape from vertices
    INSERT → block ref insertion point
    POINT → point location only
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import NamedTuple

import ezdxf
from ezdxf.document import Drawing

from core.geometry import (
    ShapeInfo,
    detect_shape_from_polygon,
    detect_shape_from_circle,
)

# ── types ────────────────────────────────────────────────────────────────────

Point = tuple[float, float]
Segment = tuple[Point, Point]
Polygon = list[Point]


class ColumnGeom(NamedTuple):
    """Column geometry extracted from DXF."""

    x: float
    y: float
    shape: ShapeInfo
    block_name: str = ""
    rotation: float = 0.0


class SkipEntry(NamedTuple):
    handle: str
    etype: str
    layer: str
    reason: str


@dataclass
class ImportResult:
    """Complete geometry extraction result from a DXF file."""

    # Structural — linear
    wall_segments: list[Segment] = field(default_factory=list)
    beam_segments: list[Segment] = field(default_factory=list)
    line_support_segments: list[Segment] = field(default_factory=list)
    # Structural — point
    column_geoms: list[ColumnGeom] = field(default_factory=list)
    point_support_points: list[Point] = field(default_factory=list)
    # Structural — polygon
    slab_polygons: list[Polygon] = field(default_factory=list)
    opening_polygons: list[Polygon] = field(default_factory=list)
    drop_cap_polygons: list[Polygon] = field(default_factory=list)
    drop_panel_polygons: list[Polygon] = field(default_factory=list)
    area_spring_polygons: list[Polygon] = field(default_factory=list)
    recess_polygons: list[Polygon] = field(default_factory=list)
    # Loads — NEW
    line_load_segments: list[Segment] = field(default_factory=list)
    area_load_polygons: list[Polygon] = field(default_factory=list)
    point_load_points: list[Point] = field(default_factory=list)
    # Meta
    skipped: list[SkipEntry] = field(default_factory=list)
    available_layers: list[str] = field(default_factory=list)

    # Per-layer geometry tracking for multi-instance support
    # Maps DXF layer name → list of geometry items for that layer
    layer_wall_segments: dict[str, list[Segment]] = field(default_factory=dict)
    layer_beam_segments: dict[str, list[Segment]] = field(default_factory=dict)
    layer_column_geoms: dict[str, list[ColumnGeom]] = field(default_factory=dict)
    layer_slab_polygons: dict[str, list[Polygon]] = field(default_factory=dict)
    layer_opening_polygons: dict[str, list[Polygon]] = field(default_factory=dict)
    layer_drop_cap_polygons: dict[str, list[Polygon]] = field(default_factory=dict)
    layer_drop_panel_polygons: dict[str, list[Polygon]] = field(default_factory=dict)
    layer_point_support_points: dict[str, list[Point]] = field(default_factory=dict)
    layer_line_support_segments: dict[str, list[Segment]] = field(default_factory=dict)
    layer_area_spring_polygons: dict[str, list[Polygon]] = field(default_factory=dict)
    layer_recess_polygons: dict[str, list[Polygon]] = field(default_factory=dict)
    layer_line_load_segments: dict[str, list[Segment]] = field(default_factory=dict)
    layer_area_load_polygons: dict[str, list[Polygon]] = field(default_factory=dict)
    layer_point_load_points: dict[str, list[Point]] = field(default_factory=dict)


# ── helpers ──────────────────────────────────────────────────────────────────


def _round(v: float, n: int = 6) -> float:
    return round(float(v), n)


def _rpt(p, n: int = 6) -> Point:
    return (_round(p[0], n), _round(p[1], n))


def _pts_from_lwpolyline(e) -> list[Point]:
    return [(_round(p[0]), _round(p[1])) for p in e.get_points()]


def _pts_from_polyline_2d(e) -> list[Point]:
    return [(_round(v.dxf.location.x), _round(v.dxf.location.y)) for v in e.vertices]


def _is_closed_lwpoly(e) -> bool:
    return bool(e.closed)


def _is_closed_poly(e) -> bool:
    return bool(e.is_closed)


def _segment_list(pts: list[Point], closed: bool) -> list[Segment]:
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if closed and len(pts) > 1:
        segs.append((pts[-1], pts[0]))
    return segs


def _spline_to_pts(e, n: int = 64) -> list[Point]:
    """Sample a SPLINE entity at n points."""
    try:
        spline = e.construction_tool()
        params = [spline.t0 + i * (spline.t1 - spline.t0) / (n - 1) for i in range(n)]
        return [(_round(p.x), _round(p.y)) for p in (spline.point(t) for t in params)]
    except Exception:
        return []


def _polygon_from_hatch(e) -> list[Polygon]:
    """Extract closed boundary loops from a HATCH entity."""
    polys: list[Polygon] = []
    try:
        for path in e.paths:
            pts: list[Point] = []
            if hasattr(path, "vertices"):
                pts = [(_round(v[0]), _round(v[1])) for v in path.vertices]
            elif hasattr(path, "edges"):
                for edge in path.edges:
                    if edge.EDGE_TYPE == "LineEdge":
                        pts.append((_round(edge.start[0]), _round(edge.start[1])))
            if len(pts) >= 3:
                polys.append(pts)
    except Exception:
        pass
    return polys


# Roles grouped by geometry type
LINEAR_ROLES = {"wall", "beam", "line_support", "lineload"}
POLYGON_ROLES = {"slab", "opening", "drop_cap", "drop_panel", "area_spring", "recess", "areaload"}
POINT_ROLES = {"point_support", "pointload"}
COLUMN_ROLE = "column"


# ── public API ───────────────────────────────────────────────────────────────


def list_layers(dxf_path: str) -> list[str]:
    """Return all layer names in the file, sorted."""
    doc = ezdxf.readfile(dxf_path)
    return sorted(layer.dxf.name for layer in doc.layers)


def import_dxf(
    dxf_path: str,
    active_layers: dict[str, str],  # DXF layer name → role
    unit_scale: float = 1.0,
    dedupe_tol: int = 6,
) -> ImportResult:
    """
    Read a DXF file and extract geometry for all mapped layers.

    Parameters
    ----------
    dxf_path      : path to the DXF file
    active_layers : dict mapping DXF layer name (case-sensitive) → role string
    unit_scale    : DXF-unit → metre conversion factor
    dedupe_tol    : decimal places for dedup

    Returns
    -------
    ImportResult with all geometry lists populated.
    """
    doc: Drawing = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    result = ImportResult()
    result.available_layers = sorted(layer.dxf.name for layer in doc.layers)

    # Build case-insensitive lookup
    active: dict[str, tuple[str, str]] = {}  # lower_name → (role, orig_name)
    for layer_name, role in active_layers.items():
        active[layer_name.lower()] = (role, layer_name)

    # Dedup sets for linear segments
    seen_segs: dict[str, set] = {}

    def scale(v: float) -> float:
        return _round(v * unit_scale, dedupe_tol)

    def spt(p: Point) -> Point:
        return (scale(p[0]), scale(p[1]))

    def _add_to_layer_list(mapping: dict, layer_name: str, item):
        mapping.setdefault(layer_name, []).append(item)

    def add_segment(role: str, layer_name: str, p0: Point, p1: Point):
        s0, s1 = spt(p0), spt(p1)
        if s0 == s1:
            return
        key = tuple(sorted((s0, s1)))
        role_set = seen_segs.setdefault(role, set())
        if key in role_set:
            return
        role_set.add(key)
        seg = (s0, s1)

        if role == "wall":
            result.wall_segments.append(seg)
            _add_to_layer_list(result.layer_wall_segments, layer_name, seg)
        elif role == "beam":
            result.beam_segments.append(seg)
            _add_to_layer_list(result.layer_beam_segments, layer_name, seg)
        elif role == "line_support":
            result.line_support_segments.append(seg)
            _add_to_layer_list(result.layer_line_support_segments, layer_name, seg)
        elif role == "lineload":
            result.line_load_segments.append(seg)
            _add_to_layer_list(result.layer_line_load_segments, layer_name, seg)

    def add_polygon(role: str, layer_name: str, pts: list[Point]):
        scaled = [spt(p) for p in pts]
        if len(scaled) < 3:
            return
        if role == "slab":
            result.slab_polygons.append(scaled)
            _add_to_layer_list(result.layer_slab_polygons, layer_name, scaled)
        elif role == "opening":
            result.opening_polygons.append(scaled)
            _add_to_layer_list(result.layer_opening_polygons, layer_name, scaled)
        elif role == "drop_cap":
            result.drop_cap_polygons.append(scaled)
            _add_to_layer_list(result.layer_drop_cap_polygons, layer_name, scaled)
        elif role == "drop_panel":
            result.drop_panel_polygons.append(scaled)
            _add_to_layer_list(result.layer_drop_panel_polygons, layer_name, scaled)
        elif role == "area_spring":
            result.area_spring_polygons.append(scaled)
            _add_to_layer_list(result.layer_area_spring_polygons, layer_name, scaled)
        elif role == "recess":
            result.recess_polygons.append(scaled)
            _add_to_layer_list(result.layer_recess_polygons, layer_name, scaled)
        elif role == "areaload":
            result.area_load_polygons.append(scaled)
            _add_to_layer_list(result.layer_area_load_polygons, layer_name, scaled)

    def add_point(role: str, layer_name: str, x: float, y: float):
        sx, sy = scale(x), scale(y)
        pt = (sx, sy)
        if role == "point_support":
            result.point_support_points.append(pt)
            _add_to_layer_list(result.layer_point_support_points, layer_name, pt)
        elif role == "pointload":
            result.point_load_points.append(pt)
            _add_to_layer_list(result.layer_point_load_points, layer_name, pt)

    def add_column(
        layer_name: str,
        x: float,
        y: float,
        shape: ShapeInfo,
        block_name: str = "",
        rotation: float = 0.0,
    ):
        sx, sy = scale(x), scale(y)
        # Scale shape dimensions
        scaled_shape = ShapeInfo(
            is_circular=shape.is_circular,
            width=scale(shape.width) if shape.width else 0,
            depth=scale(shape.depth) if shape.depth else 0,
            diameter=scale(shape.diameter) if shape.diameter else 0,
            center_x=sx,
            center_y=sy,
            angle=shape.angle,
        )
        cg = ColumnGeom(sx, sy, scaled_shape, block_name, rotation)
        result.column_geoms.append(cg)
        _add_to_layer_list(result.layer_column_geoms, layer_name, cg)

    # ── Main entity loop ─────────────────────────────────────────────────────
    for e in msp:
        layer_name_raw = e.dxf.layer
        if layer_name_raw.lower() not in active:
            continue
        role, orig_layer = active[layer_name_raw.lower()]
        etype = e.dxftype()
        handle = e.dxf.handle

        # ── COLUMN entities ──────────────────────────────────────────────────
        if role == COLUMN_ROLE:
            if etype == "CIRCLE":
                c = e.dxf.center
                r = e.dxf.radius
                shape = detect_shape_from_circle(c.x, c.y, r)
                add_column(orig_layer, c.x, c.y, shape)
            elif etype == "LWPOLYLINE":
                pts = _pts_from_lwpolyline(e)
                if pts and _is_closed_lwpoly(e):
                    shape = detect_shape_from_polygon(pts)
                    add_column(orig_layer, shape.center_x, shape.center_y, shape)
                elif pts:
                    # Open polyline — use centroid as point
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    shape = detect_shape_from_polygon(pts)
                    add_column(orig_layer, cx, cy, shape)
            elif etype == "POLYLINE" and e.is_2d_polyline:
                pts = _pts_from_polyline_2d(e)
                if pts:
                    shape = detect_shape_from_polygon(pts)
                    add_column(orig_layer, shape.center_x, shape.center_y, shape)
            elif etype == "POINT":
                loc = e.dxf.location
                shape = ShapeInfo(center_x=loc.x, center_y=loc.y)
                add_column(orig_layer, loc.x, loc.y, shape)
            elif etype == "INSERT":
                ins = e.dxf.insert
                name = e.dxf.get("name", "")
                rot = float(e.dxf.get("rotation", 0.0))
                shape = ShapeInfo(center_x=ins.x, center_y=ins.y, angle=rot)
                add_column(
                    orig_layer, ins.x, ins.y, shape, block_name=name, rotation=rot
                )
            else:
                result.skipped.append(
                    SkipEntry(
                        handle, etype, layer_name_raw, f"Unsupported column entity"
                    )
                )

        # ── LINEAR entities ──────────────────────────────────────────────────
        elif role in LINEAR_ROLES:
            if etype == "LINE":
                add_segment(
                    role,
                    orig_layer,
                    (e.dxf.start.x, e.dxf.start.y),
                    (e.dxf.end.x, e.dxf.end.y),
                )
            elif etype == "LWPOLYLINE":
                pts = _pts_from_lwpolyline(e)
                closed = _is_closed_lwpoly(e)
                for s in _segment_list(pts, closed):
                    add_segment(role, orig_layer, s[0], s[1])
            elif etype == "POLYLINE" and e.is_2d_polyline:
                pts = _pts_from_polyline_2d(e)
                closed = _is_closed_poly(e)
                for s in _segment_list(pts, closed):
                    add_segment(role, orig_layer, s[0], s[1])
            else:
                result.skipped.append(
                    SkipEntry(
                        handle,
                        etype,
                        layer_name_raw,
                        f"Unsupported linear entity on '{role}' layer",
                    )
                )

        # ── POLYGON entities ─────────────────────────────────────────────────
        elif role in POLYGON_ROLES:
            if etype == "LWPOLYLINE":
                pts = _pts_from_lwpolyline(e)
                if _is_closed_lwpoly(e) or (len(pts) >= 3 and pts[0] == pts[-1]):
                    if pts and pts[0] == pts[-1]:
                        pts = pts[:-1]
                    add_polygon(role, orig_layer, pts)
                else:
                    add_polygon(role, orig_layer, pts)
            elif etype == "POLYLINE" and e.is_2d_polyline:
                pts = _pts_from_polyline_2d(e)
                if pts and pts[0] == pts[-1]:
                    pts = pts[:-1]
                add_polygon(role, orig_layer, pts)
            elif etype == "HATCH":
                for poly in _polygon_from_hatch(e):
                    add_polygon(role, orig_layer, poly)
            elif etype == "SPLINE":
                pts = _spline_to_pts(e)
                if pts:
                    add_polygon(role, orig_layer, pts)
            elif etype in ("SOLID", "3DFACE"):
                corners = [
                    (e.dxf.vtx0.x, e.dxf.vtx0.y),
                    (e.dxf.vtx1.x, e.dxf.vtx1.y),
                    (e.dxf.vtx2.x, e.dxf.vtx2.y),
                    (e.dxf.vtx3.x, e.dxf.vtx3.y),
                ]
                pts = list(dict.fromkeys(corners))
                add_polygon(role, orig_layer, pts)
            else:
                result.skipped.append(
                    SkipEntry(
                        handle,
                        etype,
                        layer_name_raw,
                        f"Unsupported polygon entity on '{role}' layer",
                    )
                )

        # ── POINT entities ───────────────────────────────────────────────────
        elif role in POINT_ROLES:
            if etype == "POINT":
                loc = e.dxf.location
                add_point(role, orig_layer, loc.x, loc.y)
            elif etype == "CIRCLE":
                c = e.dxf.center
                add_point(role, orig_layer, c.x, c.y)
            elif etype == "INSERT":
                ins = e.dxf.insert
                add_point(role, orig_layer, ins.x, ins.y)
            else:
                result.skipped.append(
                    SkipEntry(
                        handle,
                        etype,
                        layer_name_raw,
                        f"Unsupported point entity on '{role}' layer",
                    )
                )

    return result


# ── CLI self-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "Simple.dxf"
    print(f"Scanning: {path}")
    layers = list_layers(path)
    print(f"Layers: {layers}")

    from core.layer_parser import parse_all_layers, create_layer_instances

    parsed = parse_all_layers(layers)
    for pl in parsed:
        if pl.is_matched:
            print(f"  ✓ {pl.layer_name} → {pl.role} (keyword: '{pl.keyword_matched}')")
            if pl.dimension_hint and pl.dimension_hint.dim1:
                print(f"      dims: {pl.dimension_hint}")
        else:
            print(f"  · {pl.layer_name} (unmatched)")
