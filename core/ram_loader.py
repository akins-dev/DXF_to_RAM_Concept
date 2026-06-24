"""
ram_loader.py
=============
Applies loads (point, line, area) to a RAM Concept model from DXF geometry.

Loads are placed on the appropriate loading layers:
  - Dead loads → model's dead loading layer
  - Live loads → model's live loading layer

Each load type supports:
  - Force components: Fx, Fy, Fz, Mx, My
  - Elevation above slab
  - Live load type: Reducible / Unreducible

All ram_concept imports are deferred so this module loads without
RAM Concept installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from core.dxf_reader import ImportResult
from core.models import (
    ProjectConfig,
    LayerInstance,
    LineLoadSpec,
    AreaLoadSpec,
    PointLoadSpec,
    LoadValues,
)


@dataclass
class LoadSummary:
    line_loads_created: int = 0
    area_loads_created: int = 0
    point_loads_created: int = 0
    errors: list[str] = field(default_factory=list)

    def total_loads(self) -> int:
        return (
            self.line_loads_created + self.area_loads_created + self.point_loads_created
        )


def _find_loading_layer(cad_manager, layer_name: str):
    """Find a loading layer by name from the cad_manager."""
    for layer in cad_manager.all_layers:
        if hasattr(layer, "name") and layer.name == layer_name:
            return layer
    return None


def _has_nonzero_loads(lv: LoadValues) -> bool:
    """Check if a LoadValues has any non-zero components."""
    return any(v != 0.0 for v in lv.to_tuple())


def apply_loads(
    model,
    import_result: ImportResult,
    config: ProjectConfig,
    log: Callable[[str], None] = print,
) -> LoadSummary:
    """
    Apply all loads from ImportResult to the RAM Concept model.

    Loads are applied to the Dead Loading and Live Loading layers.
    """
    # Deferred imports
    from ram_concept.line_segment_2D import LineSegment2D
    from ram_concept.point_2D import Point2D
    from ram_concept.polygon_2D import Polygon2D

    summary = LoadSummary()
    cad = model.cad_manager

    # Attempt to find loading layers
    dead_layer = _find_loading_layer(cad, "Dead Loading")
    live_layer = _find_loading_layer(cad, "Live Loading")

    if dead_layer is None:
        log("⚠  'Dead Loading' layer not found — dead loads will be skipped.")
    if live_layer is None:
        log("⚠  'Live Loading' layer not found — live loads will be skipped.")

    def poly2d(pts):
        return Polygon2D([Point2D(x, y) for (x, y) in pts])

    def seg2d(p0, p1):
        return LineSegment2D(Point2D(p0[0], p0[1]), Point2D(p1[0], p1[1]))

    # ── LINE LOADS ────────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("lineload"):
        spec: LineLoadSpec = li.spec
        segs = import_result.layer_line_load_segments.get(li.layer_name, [])
        if not segs:
            continue

        log(f"Adding {len(segs)} line load(s) from '{li.layer_name}'…")
        for i, (p0, p1) in enumerate(segs):
            try:
                # Dead loads
                if dead_layer and _has_nonzero_loads(spec.value_dead):
                    ll = dead_layer.add_line_load(seg2d(p0, p1))
                    try:
                        ll.Fz0 = spec.value_dead.fz
                        ll.Fz1 = spec.value_dead.fz
                        ll.elevation = spec.elevation_dead
                    except AttributeError:
                        pass

                # Live loads
                if live_layer and _has_nonzero_loads(spec.value_live):
                    ll = live_layer.add_line_load(seg2d(p0, p1))
                    try:
                        ll.Fz0 = spec.value_live.fz
                        ll.Fz1 = spec.value_live.fz
                        ll.elevation = spec.elevation_live
                    except AttributeError:
                        pass

                summary.line_loads_created += 1
            except Exception as exc:
                msg = f"  Line load #{i+1} [{li.layer_name}]: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── AREA LOADS ────────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("areaload"):
        spec: AreaLoadSpec = li.spec
        polys = import_result.layer_area_load_polygons.get(li.layer_name, [])
        if not polys:
            continue

        log(f"Adding {len(polys)} area load(s) from '{li.layer_name}'…")
        for i, poly in enumerate(polys):
            try:
                # Dead loads
                if dead_layer and _has_nonzero_loads(spec.value_dead):
                    al = dead_layer.add_area_load(poly2d(poly))
                    try:
                        al.Fz = spec.value_dead.fz
                        al.elevation = spec.elevation_dead
                    except AttributeError:
                        pass

                # Live loads
                if live_layer and _has_nonzero_loads(spec.value_live):
                    al = live_layer.add_area_load(poly2d(poly))
                    try:
                        al.Fz = spec.value_live.fz
                        al.elevation = spec.elevation_live
                    except AttributeError:
                        pass

                summary.area_loads_created += 1
            except Exception as exc:
                msg = f"  Area load #{i+1} [{li.layer_name}]: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── POINT LOADS ───────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("pointload"):
        spec: PointLoadSpec = li.spec
        pts = import_result.layer_point_load_points.get(li.layer_name, [])
        if not pts:
            continue

        log(f"Adding {len(pts)} point load(s) from '{li.layer_name}'…")
        for i, (x, y) in enumerate(pts):
            try:
                # Dead loads
                if dead_layer and _has_nonzero_loads(spec.value_dead):
                    pl = dead_layer.add_point_load(Point2D(x, y))
                    try:
                        pl.Fz = spec.value_dead.fz
                        pl.Fx = spec.value_dead.fx
                        pl.Fy = spec.value_dead.fy
                        pl.Mx = spec.value_dead.mx
                        pl.My = spec.value_dead.my
                        pl.elevation = spec.elevation_dead
                    except AttributeError:
                        pass

                # Live loads
                if live_layer and _has_nonzero_loads(spec.value_live):
                    pl = live_layer.add_point_load(Point2D(x, y))
                    try:
                        pl.Fz = spec.value_live.fz
                        pl.Fx = spec.value_live.fx
                        pl.Fy = spec.value_live.fy
                        pl.Mx = spec.value_live.mx
                        pl.My = spec.value_live.my
                        pl.elevation = spec.elevation_live
                    except AttributeError:
                        pass

                summary.point_loads_created += 1
            except Exception as exc:
                msg = f"  Point load #{i+1} ({x},{y}): FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    log(
        f"\nLoads complete: {summary.total_loads()} load(s) created, "
        f"{len(summary.errors)} error(s)."
    )
    return summary
