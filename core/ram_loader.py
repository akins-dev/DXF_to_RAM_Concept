"""
ram_loader.py
=============
Applies loads (point, line, area) to a RAM Concept model from DXF geometry.

Loads are placed on the appropriate loading layers:
  - Dead loads → "Other Dead Loading"
  - Live loads → "Live (Reducible)" or "Live (Unreducible)"

Each load type supports:
  - Force components: Fx, Fy, Fz, Mx, My
  - Elevation above slab
  - Live load type: Reducible / Unreducible

All ram_concept imports are deferred so this module loads without
RAM Concept installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.dxf_reader import ImportResult
from core.models import (
    ProjectConfig,
    LayerInstance,
    LineLoadSpec,
    AreaLoadSpec,
    PointLoadSpec,
    LoadValues,
)

# ── RAM Concept default loading layer names ──────────────────────────────────
# These must match the names shown in the RAM Concept UI exactly.
DEAD_LAYER_NAME = "Other Dead Loading"
LIVE_REDUCIBLE_LAYER_NAME = "Live (Reducible) Loading"
LIVE_UNREDUCIBLE_LAYER_NAME = "Live (Unreducible) Loading"
KN_TO_N = 1000.0


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


def _find_force_loading_layer(cad_manager, layer_name: str):
    """Find a force loading layer by name from the cad_manager."""
    try:
        return cad_manager.force_loading_layer(layer_name)
    except Exception:
        pass

    try:
        for layer in cad_manager.force_loading_layers:
            if hasattr(layer, "name") and layer.name == layer_name:
                return layer
    except AttributeError:
        pass

    # Fallback: search all_layers
    for layer in cad_manager.all_layers:
        if hasattr(layer, "name") and layer.name == layer_name:
            return layer
    return None


def _add_force_loading_layer(cad_manager, layer_name: str, loading_cause_name: str, log):
    """Create a force loading layer and set its loading cause when available."""
    try:
        layer = cad_manager.add_force_loading_layer(layer_name)
    except Exception as exc:
        log(f"⚠  Could not create '{layer_name}' layer: {exc}")
        return None

    try:
        from ram_concept.loading_layer import LoadingCause, LoadingType

        layer.loading_type = LoadingType(getattr(LoadingCause, loading_cause_name))
    except Exception as exc:
        log(
            f"⚠  Created '{layer_name}', but could not set loading type "
            f"'{loading_cause_name}': {exc}"
        )
    return layer


def _get_or_create_live_loading_layer(cad_manager, layer_name: str, log):
    """Find or create the requested live loading layer."""
    layer = _find_force_loading_layer(cad_manager, layer_name)
    if layer is not None:
        return layer

    if layer_name == LIVE_REDUCIBLE_LAYER_NAME:
        return _add_force_loading_layer(cad_manager, layer_name, "LIVE_REDUCIBLE", log)
    if layer_name == LIVE_UNREDUCIBLE_LAYER_NAME:
        return _add_force_loading_layer(cad_manager, layer_name, "LIVE_UNREDUCIBLE", log)
    return None


def _live_layer_name(live_load_type: str) -> str:
    """Map the spec's live_load_type to the correct RAM Concept layer name."""
    if str(live_load_type).lower() == "reducible":
        return LIVE_REDUCIBLE_LAYER_NAME
    return LIVE_UNREDUCIBLE_LAYER_NAME


def _has_nonzero_loads(lv: LoadValues) -> bool:
    """Check if a LoadValues has any non-zero components."""
    return any(v != 0.0 for v in lv.to_tuple())


def _api_load_values(lv: LoadValues) -> tuple[float, float, float, float, float]:
    """Convert GUI kN-based load inputs to RAM Concept SI API units.

    The local RAM Concept docs state that set_SI_API_units() uses meters and
    Newtons. The UI accepts kN, kN/m, and kN/m2, so every force/intensity and
    moment component is multiplied by 1000 before assigning it through the API.
    The UI treats Fz as a positive downward gravity-load magnitude; RAM's
    positive-sign API convention requires downward Fz loads to be negative.
    """
    return (
        lv.fx * KN_TO_N,
        lv.fy * KN_TO_N,
        -abs(lv.fz) * KN_TO_N,
        lv.mx * KN_TO_N,
        lv.my * KN_TO_N,
    )


def _set_load_values(load, lv: LoadValues, elevation: float) -> None:
    """Apply all load components using the documented RAM Concept API."""
    load.elevation = elevation
    if hasattr(load, "set_load_values"):
        load.set_load_values(*_api_load_values(lv))
        return

    # PointLoad has no documented set_load_values(); docs show zero then assign.
    if hasattr(load, "zero_load_values"):
        load.zero_load_values()
    fx, fy, fz, mx, my = _api_load_values(lv)
    load.Fx = fx
    load.Fy = fy
    load.Fz = fz
    load.Mx = mx
    load.My = my


def apply_loads(
    model,
    import_result: ImportResult,
    config: ProjectConfig,
    log: Callable[[str], None] = print,
) -> LoadSummary:
    """
    Apply all loads from ImportResult to the RAM Concept model.

    Loads are applied to the correct RAM Concept loading layers:
      - Dead → "Other Dead Loading"
      - Live → "Live (Reducible)" or "Live (Unreducible)" per spec
    """
    # Deferred imports
    from ram_concept.line_segment_2D import LineSegment2D
    from ram_concept.point_2D import Point2D
    from ram_concept.polygon_2D import Polygon2D

    summary = LoadSummary()
    cad = model.cad_manager

    # ── Set SI API units and positive signs ───────────────────────────────────
    # build_structure() restores original units when it finishes, so we must
    # re-set them here for load values to be interpreted correctly.
    units = model.units
    signs = model.signs
    saved_units = units.get_units()
    saved_signs = signs.get_signs()
    units.set_SI_API_units()
    signs.set_positive_signs()

    try:
        # ── Find loading layers ──────────────────────────────────────────────
        dead_layer = _find_force_loading_layer(cad, DEAD_LAYER_NAME)
        live_red_layer = _find_force_loading_layer(cad, LIVE_REDUCIBLE_LAYER_NAME)
        live_unred_layer = _find_force_loading_layer(cad, LIVE_UNREDUCIBLE_LAYER_NAME)

        if dead_layer is None:
            log(f"⚠  '{DEAD_LAYER_NAME}' layer not found — dead loads will be skipped.")
        if live_red_layer is None:
            log(f"⚠  '{LIVE_REDUCIBLE_LAYER_NAME}' layer not found.")
        if live_unred_layer is None:
            log(
                f"  '{LIVE_UNREDUCIBLE_LAYER_NAME}' layer not found yet; "
                "it will be created if an unreducible live load is selected."
            )

        # Log discovered layers for debugging
        try:
            layer_names = [
                getattr(l, "name", "?") for l in cad.force_loading_layers
            ]
            log(f"  Available force loading layers: {layer_names}")
        except AttributeError:
            pass

        def _get_live_layer(spec):
            """Get the correct live layer based on the spec's live_load_type."""
            layer_name = _live_layer_name(getattr(spec, "live_load_type", "Reducible"))
            return _get_or_create_live_loading_layer(cad, layer_name, log)

        def poly2d(pts):
            return Polygon2D([Point2D(x, y) for (x, y) in pts])

        def seg2d(p0, p1):
            return LineSegment2D(Point2D(p0[0], p0[1]), Point2D(p1[0], p1[1]))

        # ── LINE LOADS ───────────────────────────────────────────────────────
        for li in config.enabled_instances_by_role("lineload"):
            spec: LineLoadSpec = li.spec
            segs = import_result.layer_line_load_segments.get(li.layer_name, [])
            if not segs:
                continue

            live_layer = _get_live_layer(spec)
            log(f"Adding {len(segs)} line load(s) from '{li.layer_name}'…")
            for i, (p0, p1) in enumerate(segs):
                try:
                    # Dead loads
                    if dead_layer and _has_nonzero_loads(spec.value_dead):
                        ll = dead_layer.add_line_load(seg2d(p0, p1))
                        _set_load_values(ll, spec.value_dead, spec.elevation_dead)

                    # Live loads
                    if live_layer and _has_nonzero_loads(spec.value_live):
                        ll = live_layer.add_line_load(seg2d(p0, p1))
                        _set_load_values(ll, spec.value_live, spec.elevation_live)

                    summary.line_loads_created += 1
                except Exception as exc:
                    msg = f"  Line load #{i+1} [{li.layer_name}]: FAILED – {exc}"
                    summary.errors.append(msg)
                    log(msg)

        # ── AREA LOADS ───────────────────────────────────────────────────────
        for li in config.enabled_instances_by_role("areaload"):
            spec: AreaLoadSpec = li.spec
            polys = import_result.layer_area_load_polygons.get(li.layer_name, [])
            if not polys:
                continue

            live_layer = _get_live_layer(spec)
            log(f"Adding {len(polys)} area load(s) from '{li.layer_name}'…")
            for i, poly in enumerate(polys):
                try:
                    # Dead loads
                    if dead_layer and _has_nonzero_loads(spec.value_dead):
                        al = dead_layer.add_area_load(poly2d(poly))
                        _set_load_values(al, spec.value_dead, spec.elevation_dead)

                    # Live loads
                    if live_layer and _has_nonzero_loads(spec.value_live):
                        al = live_layer.add_area_load(poly2d(poly))
                        _set_load_values(al, spec.value_live, spec.elevation_live)

                    summary.area_loads_created += 1
                except Exception as exc:
                    msg = f"  Area load #{i+1} [{li.layer_name}]: FAILED – {exc}"
                    summary.errors.append(msg)
                    log(msg)

        # ── POINT LOADS ──────────────────────────────────────────────────────
        for li in config.enabled_instances_by_role("pointload"):
            spec: PointLoadSpec = li.spec
            pts = import_result.layer_point_load_points.get(li.layer_name, [])
            if not pts:
                continue

            live_layer = _get_live_layer(spec)
            log(f"Adding {len(pts)} point load(s) from '{li.layer_name}'…")
            for i, (x, y) in enumerate(pts):
                try:
                    # Dead loads
                    if dead_layer and _has_nonzero_loads(spec.value_dead):
                        pl = dead_layer.add_point_load(Point2D(x, y))
                        _set_load_values(pl, spec.value_dead, spec.elevation_dead)

                    # Live loads
                    if live_layer and _has_nonzero_loads(spec.value_live):
                        pl = live_layer.add_point_load(Point2D(x, y))
                        _set_load_values(pl, spec.value_live, spec.elevation_live)

                    summary.point_loads_created += 1
                except Exception as exc:
                    msg = f"  Point load #{i+1} ({x},{y}): FAILED – {exc}"
                    summary.errors.append(msg)
                    log(msg)

    finally:
        # ── Restore units and signs ──────────────────────────────────────────
        try:
            units.set_units(saved_units)
            signs.set_signs(saved_signs)
        except Exception:
            pass

    log(
        f"\nLoads complete: {summary.total_loads()} load(s) created, "
        f"{len(summary.errors)} error(s)."
    )
    return summary
