"""
dxf_importer.py
===============
Reads a DXF file and extracts geometry for every structural element type
defined in layer_config.DEFAULT_LAYER_MAP.

Outputs per element role
------------------------
walls        -> list of Segment  ((x0,y0),(x1,y1))
columns      -> list of ColPoint (x, y, block_name, rotation_deg)
slabs        -> list of Polygon  [(x,y), ...]
beams        -> list of Segment  (same as walls but role = beam)
openings     -> list of Polygon  [(x,y), ...]
drop_caps    -> list of Polygon
drop_panels  -> list of Polygon
point_supports -> list of (x, y)
line_supports  -> list of Segment
area_springs   -> list of Polygon

All coordinate values are in the DXF's native units.  The builder applies
the unit_scale afterwards so that each element's own scaling is centralised.

Supported entity types per role
--------------------------------
Linear (wall / beam / line_support):
  LINE, LWPOLYLINE, POLYLINE (2-D)  — polylines split into edge segments
Polygon (slab / opening / drop_cap / drop_panel / area_spring):
  LWPOLYLINE (closed), POLYLINE (closed), HATCH (boundary loop taken),
  SPLINE (approximated with 64-point sample), SOLID / 3DFACE (as polygon)
Point (column / point_support):
  POINT, CIRCLE (centre used), INSERT (block ref – insertion point used;
  block_name and rotation stored for per-block size overrides)

Anything else on a recognised layer is reported as skipped, never silently
dropped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import NamedTuple

import ezdxf
from ezdxf.document import Drawing

# ── types ────────────────────────────────────────────────────────────────────

Point   = tuple[float, float]
Segment = tuple[Point, Point]
Polygon = list[Point]


class ColPoint(NamedTuple):
    x: float
    y: float
    block_name: str = ""        # INSERT block name (empty for POINT/CIRCLE)
    rotation: float = 0.0       # degrees (from INSERT.dxf.rotation)


class SkipEntry(NamedTuple):
    handle:  str
    etype:   str
    layer:   str
    reason:  str


@dataclass
class ImportResult:
    # linear
    wall_segments:         list[Segment]  = field(default_factory=list)
    beam_segments:         list[Segment]  = field(default_factory=list)
    line_support_segments: list[Segment]  = field(default_factory=list)
    # point
    column_points:         list[ColPoint] = field(default_factory=list)
    point_support_points:  list[Point]    = field(default_factory=list)
    # polygon
    slab_polygons:         list[Polygon]  = field(default_factory=list)
    opening_polygons:      list[Polygon]  = field(default_factory=list)
    drop_cap_polygons:     list[Polygon]  = field(default_factory=list)
    drop_panel_polygons:   list[Polygon]  = field(default_factory=list)
    area_spring_polygons:  list[Polygon]  = field(default_factory=list)
    # meta
    skipped:               list[SkipEntry] = field(default_factory=list)
    available_layers:      list[str]        = field(default_factory=list)


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
    segs = [(pts[i], pts[i+1]) for i in range(len(pts)-1)]
    if closed and len(pts) > 1:
        segs.append((pts[-1], pts[0]))
    return segs

def _dedup_segment(s: Segment) -> tuple:
    return tuple(sorted(s))

def _spline_to_pts(e, n: int = 64) -> list[Point]:
    """Sample a SPLINE entity at n points."""
    try:
        from ezdxf.math import BSpline
        spline = e.construction_tool()
        params = [spline.t0 + i*(spline.t1-spline.t0)/(n-1) for i in range(n)]
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
                # edge-based boundary: walk LINE edges only
                for edge in path.edges:
                    if edge.EDGE_TYPE == "LineEdge":
                        pts.append((_round(edge.start[0]), _round(edge.start[1])))
            if len(pts) >= 3:
                polys.append(pts)
    except Exception:
        pass
    return polys


# ── public API ───────────────────────────────────────────────────────────────

def list_layers(dxf_path: str) -> list[str]:
    """Return all layer names in the file, sorted."""
    doc = ezdxf.readfile(dxf_path)
    return sorted(layer.dxf.name for layer in doc.layers)


def import_dxf(
    dxf_path:        str,
    layer_map:       dict,          # element_role -> LayerConfig (from layer_config)
    unit_scale:      float = 1.0,   # multiply coords to get metres
    dedupe_tol:      int   = 6,     # decimal places for duplicate detection
) -> ImportResult:
    """
    Parameters
    ----------
    dxf_path   : path to the DXF file
    layer_map  : dict[role_str, LayerConfig] from layer_config.DEFAULT_LAYER_MAP
                 (or a user-edited copy of it)
    unit_scale : DXF-unit → metre conversion factor
    dedupe_tol : decimal-place tolerance for deduplicating linear segments

    Returns
    -------
    ImportResult with geometry lists ready for the builder.
    """
    doc: Drawing = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    result = ImportResult()
    result.available_layers = sorted(layer.dxf.name for layer in doc.layers)

    # Build a reverse map: DXF layer name -> (role, LayerConfig)
    active: dict[str, tuple[str, object]] = {}
    for role, cfg in layer_map.items():
        if cfg.enabled:
            active[cfg.layer.lower()] = (role, cfg)

    # Dedup sets for linear elements
    seen_segs: dict[str, set] = {
        "wall": set(), "beam": set(), "line_support": set()
    }

    def scale(v: float) -> float:
        return _round(v * unit_scale, dedupe_tol)

    def spt(p: Point) -> Point:
        return (scale(p[0]), scale(p[1]))

    def add_segment(role: str, p0: Point, p1: Point):
        s0, s1 = spt(p0), spt(p1)
        if s0 == s1:
            return
        key = tuple(sorted((s0, s1)))
        if key in seen_segs.get(role, set()):
            return
        seen_segs.setdefault(role, set()).add(key)
        seg = (s0, s1)
        if role == "wall":
            result.wall_segments.append(seg)
        elif role == "beam":
            result.beam_segments.append(seg)
        elif role == "line_support":
            result.line_support_segments.append(seg)

    def add_polygon(role: str, pts: list[Point]):
        scaled = [spt(p) for p in pts]
        if len(scaled) < 3:
            return
        if role == "slab":
            result.slab_polygons.append(scaled)
        elif role == "opening":
            result.opening_polygons.append(scaled)
        elif role == "drop_cap":
            result.drop_cap_polygons.append(scaled)
        elif role == "drop_panel":
            result.drop_panel_polygons.append(scaled)
        elif role == "area_spring":
            result.area_spring_polygons.append(scaled)

    def add_point(role: str, x: float, y: float, block_name: str = "", rotation: float = 0.0):
        sx, sy = scale(x), scale(y)
        if role == "column":
            result.column_points.append(ColPoint(sx, sy, block_name, rotation))
        elif role == "point_support":
            result.point_support_points.append((sx, sy))

    for e in msp:
        layer_name = e.dxf.layer
        if layer_name.lower() not in active:
            continue
        role, cfg = active[layer_name.lower()]
        etype = e.dxftype()
        handle = e.dxf.handle

        # ── LINEAR entities ─────────────────────────────────────────────────
        if role in ("wall", "beam", "line_support"):
            if etype == "LINE":
                add_segment(role, (e.dxf.start.x, e.dxf.start.y),
                                  (e.dxf.end.x,   e.dxf.end.y))
            elif etype == "LWPOLYLINE":
                pts    = _pts_from_lwpolyline(e)
                closed = _is_closed_lwpoly(e)
                for s in _segment_list(pts, closed):
                    add_segment(role, s[0], s[1])
            elif etype == "POLYLINE" and e.is_2d_polyline:
                pts    = _pts_from_polyline_2d(e)
                closed = _is_closed_poly(e)
                for s in _segment_list(pts, closed):
                    add_segment(role, s[0], s[1])
            else:
                result.skipped.append(SkipEntry(handle, etype, layer_name,
                    f"Unsupported linear entity on '{role}' layer"))

        # ── POLYGON entities ─────────────────────────────────────────────────
        elif role in ("slab", "opening", "drop_cap", "drop_panel", "area_spring"):
            if etype == "LWPOLYLINE":
                pts = _pts_from_lwpolyline(e)
                if _is_closed_lwpoly(e) or (len(pts) >= 3 and pts[0] == pts[-1]):
                    # remove duplicate closing vertex if present
                    if pts and pts[0] == pts[-1]:
                        pts = pts[:-1]
                    add_polygon(role, pts)
                else:
                    # open polyline on a polygon layer -- treat as boundary ring
                    add_polygon(role, pts)
            elif etype == "POLYLINE" and e.is_2d_polyline:
                pts = _pts_from_polyline_2d(e)
                if pts and pts[0] == pts[-1]:
                    pts = pts[:-1]
                add_polygon(role, pts)
            elif etype == "HATCH":
                for poly in _polygon_from_hatch(e):
                    add_polygon(role, poly)
            elif etype == "SPLINE":
                pts = _spline_to_pts(e)
                if pts:
                    add_polygon(role, pts)
            elif etype in ("SOLID", "3DFACE"):
                # SOLID/3DFACE: four corner points (p1-p4), last may == first
                corners = [
                    (e.dxf.vtx0.x, e.dxf.vtx0.y),
                    (e.dxf.vtx1.x, e.dxf.vtx1.y),
                    (e.dxf.vtx2.x, e.dxf.vtx2.y),
                    (e.dxf.vtx3.x, e.dxf.vtx3.y),
                ]
                # deduplicate coincident last point
                pts = list(dict.fromkeys(corners))
                add_polygon(role, pts)
            elif etype == "LINE":
                # Stray lines on a polygon layer -- treat as boundary edge but warn
                result.skipped.append(SkipEntry(handle, etype, layer_name,
                    f"LINE on polygon layer '{role}' -- ignored (expected closed polygon)"))
            else:
                result.skipped.append(SkipEntry(handle, etype, layer_name,
                    f"Unsupported polygon entity on '{role}' layer"))

        # ── POINT entities ────────────────────────────────────────────────────
        elif role in ("column", "point_support"):
            if etype == "POINT":
                loc = e.dxf.location
                add_point(role, loc.x, loc.y)
            elif etype == "CIRCLE":
                c = e.dxf.center
                add_point(role, c.x, c.y)
            elif etype == "INSERT":
                ins  = e.dxf.insert
                name = e.dxf.get("name", "")
                rot  = float(e.dxf.get("rotation", 0.0))
                add_point(role, ins.x, ins.y, block_name=name, rotation=rot)
            elif etype == "LWPOLYLINE":
                # closed rectangle drawn around a column -- use centroid
                pts = _pts_from_lwpolyline(e)
                if pts:
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    add_point(role, cx, cy)
            else:
                result.skipped.append(SkipEntry(handle, etype, layer_name,
                    f"Unsupported point entity on '{role}' layer"))

    return result


# ── CLI self-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from layer_config import DEFAULT_LAYER_MAP

    path = sys.argv[1] if len(sys.argv) > 1 else "Simple.dxf"
    print(f"Scanning: {path}")
    print("Layers found:", list_layers(path))

    r = import_dxf(path, DEFAULT_LAYER_MAP, unit_scale=1.0)
    print(f"  Wall segments   : {len(r.wall_segments)}")
    print(f"  Beam segments   : {len(r.beam_segments)}")
    print(f"  Columns         : {len(r.column_points)}")
    print(f"  Slab polygons   : {len(r.slab_polygons)}")
    print(f"  Openings        : {len(r.opening_polygons)}")
    print(f"  Drop caps       : {len(r.drop_cap_polygons)}")
    print(f"  Drop panels     : {len(r.drop_panel_polygons)}")
    print(f"  Point supports  : {len(r.point_support_points)}")
    print(f"  Line supports   : {len(r.line_support_segments)}")
    print(f"  Area springs    : {len(r.area_spring_polygons)}")
    if r.skipped:
        print("  Skipped entities:")
        for s in r.skipped:
            print(f"    [{s.etype}] handle={s.handle} layer='{s.layer}': {s.reason}")
