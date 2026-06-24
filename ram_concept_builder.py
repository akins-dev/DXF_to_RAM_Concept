"""
ram_concept_builder.py
======================
Consumes an ImportResult from dxf_importer and builds the full RAM Concept
model via the official Python scripting API.

Supported elements
------------------
  Mesh-Input layer objects
    • Slab areas          (add_slab_area)
    • Walls               (add_wall)
    • Columns             (add_column)
    • Beams               (add_beam)
    • Slab openings       (add_slab_opening)
    • Drop caps           (add_slab_area  – priority 3)
    • Drop panels         (add_slab_area  – priority 2)
    • Point supports      (add_point_support)
    • Line supports       (add_line_support)
    • Area springs        (add_area_spring)

All ram_concept imports are deferred to build_structure() so this module
loads fine on a machine without RAM Concept installed.

Coordinate convention
---------------------
Everything is in metres (SI API units). The builder calls
  model.units.set_SI_API_units()
before doing any geometry work, and restores user units at the end.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable, Optional

from dxf_importer import ImportResult
from layer_config import (
    SlabSpec, WallSpec, ColumnSpec, BeamSpec,
    OpeningSpec, DropCapSpec, DropPanelSpec,
    PointSupportSpec, LineSupportSpec, AreaSpringSpec,
    DESIGN_CODES, STRUCTURE_TYPES,
)


# ── Summary returned to the GUI ───────────────────────────────────────────────

@dataclass
class BuildSummary:
    slabs_created:          int = 0
    walls_created:          int = 0
    columns_created:        int = 0
    beams_created:          int = 0
    openings_created:       int = 0
    drop_caps_created:      int = 0
    drop_panels_created:    int = 0
    point_supports_created: int = 0
    line_supports_created:  int = 0
    area_springs_created:   int = 0
    errors:  list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def total_objects(self) -> int:
        return (self.slabs_created + self.walls_created + self.columns_created
                + self.beams_created + self.openings_created
                + self.drop_caps_created + self.drop_panels_created
                + self.point_supports_created + self.line_supports_created
                + self.area_springs_created)


# ── Concrete helper ───────────────────────────────────────────────────────────

def _get_concrete(concretes, name: str):
    """Look up a concrete mix; raise ValueError with a friendly message."""
    try:
        return concretes.concrete(name)
    except Exception as exc:
        raise ValueError(
            f"Concrete mix '{name}' not found in model.\n"
            "Either the name does not match what was added, or add_concrete() "
            "was not called before build_structure()."
        ) from exc


def _polygon_to_polygon2d(Polygon2D, Point2D, pts):
    return Polygon2D([Point2D(x, y) for (x, y) in pts])


def _line_to_segment2d(LineSegment2D, Point2D, p0, p1):
    return LineSegment2D(Point2D(p0[0], p0[1]), Point2D(p1[0], p1[1]))


# ── Concrete setup (convenience, call from the GUI thread before build) ───────

def add_concrete_mix(
    model,
    fc_mpa: float,
    name: Optional[str] = None,
    poissons_ratio: float = 0.2,
    unit_mass: float = 2450.0,          # kg/m³
    unit_mass_loads: float = 2500.0,    # kg/m³ (self-weight density)
    use_code_Ec: bool = True,
    fc_initial_ratio: float = 0.75,
    delete_others: bool = True,
) -> str:
    """
    Add one concrete mix to the model and (optionally) delete all others.
    Returns the concrete name string used, for feeding into the Spec objects.
    """
    concrete_name = name or f"C{int(fc_mpa)}"
    concretes = model.concretes
    c = concretes.add_concrete(concrete_name)
    c.fc_final               = fc_mpa               # MPa (user units)
    c.fc_initial             = fc_mpa * fc_initial_ratio
    c.poissons_ratio         = poissons_ratio
    c.unit_mass              = unit_mass
    c.unit_unit_mass_for_loads = unit_mass_loads
    c.use_code_Ec            = use_code_Ec

    if delete_others:
        for other in list(concretes.concretes):
            if other.name != concrete_name:
                try:
                    other.delete()
                except Exception:
                    pass
    return concrete_name


# ── Main builder function ─────────────────────────────────────────────────────

def build_structure(
    model,
    import_result: ImportResult,
    layer_map:     dict,                 # role -> LayerConfig
    log: Callable[[str], None] = print,
    mesh_after: bool = True,
) -> BuildSummary:
    """
    Populate the RAM Concept model from ImportResult geometry.

    Parameters
    ----------
    model         : live ram_concept.model.Model
    import_result : output of dxf_importer.import_dxf()
    layer_map     : dict[role_str, LayerConfig]  from layer_config
    log           : callable that receives progress strings
    mesh_after    : call model.generate_mesh() when done (requires ≥1 slab)

    Returns
    -------
    BuildSummary
    """
    # ── deferred imports (so this module loads without RAM Concept installed)
    from ram_concept.line_segment_2D import LineSegment2D
    from ram_concept.point_2D        import Point2D
    from ram_concept.polygon_2D      import Polygon2D

    summary  = BuildSummary()
    cad      = model.cad_manager
    sl       = cad.structure_layer          # mesh-input structure layer
    concretes = model.concretes

    # ── save & switch to SI API units ────────────────────────────────────────
    units = model.units
    signs = model.signs
    saved_units = units.get_units()
    saved_signs = signs.get_signs()
    units.set_SI_API_units()
    signs.set_positive_signs()

    # ── helper: poly / segment factories ─────────────────────────────────────
    def poly2d(pts):
        return _polygon_to_polygon2d(Polygon2D, Point2D, pts)

    def seg2d(p0, p1):
        return _line_to_segment2d(LineSegment2D, Point2D, p0, p1)

    # ── 1  SLAB AREAS ────────────────────────────────────────────────────────
    cfg_slab = layer_map.get("slab")
    if cfg_slab and cfg_slab.enabled and import_result.slab_polygons:
        spec: SlabSpec = cfg_slab.spec
        conc = _get_concrete(concretes, spec.concrete_name)
        da   = cad.default_slab_area
        da.thickness  = spec.thickness
        da.toc        = spec.toc
        da.concrete   = conc
        da.priority   = spec.priority
        log(f"Adding {len(import_result.slab_polygons)} slab area(s)…")
        for i, poly in enumerate(import_result.slab_polygons):
            try:
                sl.add_slab_area(poly2d(poly))
                summary.slabs_created += 1
            except Exception as exc:
                msg = f"  Slab #{i+1}: FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    elif not import_result.slab_polygons:
        log("⚠  No slab polygons found – RAM Concept will refuse to mesh without a slab area.")
    log(f"  Slabs created: {summary.slabs_created}")

    # ── 2  DROP PANELS ───────────────────────────────────────────────────────
    cfg_dp = layer_map.get("drop_panel")
    if cfg_dp and cfg_dp.enabled and import_result.drop_panel_polygons:
        spec: DropPanelSpec = cfg_dp.spec
        conc = _get_concrete(concretes, spec.concrete_name)
        da   = cad.default_slab_area
        da.thickness = spec.thickness
        da.toc       = spec.toc
        da.concrete  = conc
        da.priority  = spec.priority
        log(f"Adding {len(import_result.drop_panel_polygons)} drop panel(s)…")
        for i, poly in enumerate(import_result.drop_panel_polygons):
            try:
                sl.add_slab_area(poly2d(poly))
                summary.drop_panels_created += 1
            except Exception as exc:
                msg = f"  Drop panel #{i+1}: FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Drop panels created: {summary.drop_panels_created}")

    # ── 3  DROP CAPS ─────────────────────────────────────────────────────────
    cfg_dc = layer_map.get("drop_cap")
    if cfg_dc and cfg_dc.enabled and import_result.drop_cap_polygons:
        spec: DropCapSpec = cfg_dc.spec
        conc = _get_concrete(concretes, spec.concrete_name)
        da   = cad.default_slab_area
        da.thickness = spec.thickness
        da.toc       = spec.toc
        da.concrete  = conc
        da.priority  = spec.priority
        log(f"Adding {len(import_result.drop_cap_polygons)} drop cap(s)…")
        for i, poly in enumerate(import_result.drop_cap_polygons):
            try:
                sl.add_slab_area(poly2d(poly))
                summary.drop_caps_created += 1
            except Exception as exc:
                msg = f"  Drop cap #{i+1}: FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Drop caps created: {summary.drop_caps_created}")

    # ── 4  SLAB OPENINGS ─────────────────────────────────────────────────────
    cfg_op = layer_map.get("opening")
    if cfg_op and cfg_op.enabled and import_result.opening_polygons:
        log(f"Adding {len(import_result.opening_polygons)} slab opening(s)…")
        for i, poly in enumerate(import_result.opening_polygons):
            try:
                sl.add_slab_opening(poly2d(poly))
                summary.openings_created += 1
            except Exception as exc:
                msg = f"  Opening #{i+1}: FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Openings created: {summary.openings_created}")

    # ── 5  WALLS ─────────────────────────────────────────────────────────────
    cfg_wall = layer_map.get("wall")
    if cfg_wall and cfg_wall.enabled and import_result.wall_segments:
        spec: WallSpec = cfg_wall.spec
        conc = _get_concrete(concretes, spec.concrete_name)
        dw   = cad.default_wall
        dw.thickness  = spec.thickness
        dw.height     = spec.height
        dw.below_slab = spec.below_slab
        dw.shear_wall = spec.shear_wall
        dw.compressible = spec.compressible
        dw.concrete   = conc
        dw.fixed_near = spec.fixed_near
        dw.fixed_far  = spec.fixed_far
        try:
            dw.i_factor   = spec.i_factor
        except AttributeError:
            pass   # older API version may not expose this
        dw.use_specified_LLR_parameters = False
        log(f"Adding {len(import_result.wall_segments)} wall segment(s)…")
        for i, (p0, p1) in enumerate(import_result.wall_segments):
            try:
                sl.add_wall(seg2d(p0, p1))
                summary.walls_created += 1
            except Exception as exc:
                msg = f"  Wall #{i+1} {p0}→{p1}: FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Walls created: {summary.walls_created}")

    # ── 6  BEAMS ─────────────────────────────────────────────────────────────
    cfg_beam = layer_map.get("beam")
    if cfg_beam and cfg_beam.enabled and import_result.beam_segments:
        spec: BeamSpec = cfg_beam.spec
        conc = _get_concrete(concretes, spec.concrete_name)
        db   = cad.default_beam
        db.width      = spec.width
        db.depth      = spec.depth
        db.toc        = spec.toc
        db.concrete   = conc
        db.priority   = spec.priority
        try:
            db.mesh_as_slab = spec.mesh_as_slab
        except AttributeError:
            pass   # older API version may not expose this
        try:
            db.no_torsion = spec.no_torsion
        except AttributeError:
            pass
        log(f"Adding {len(import_result.beam_segments)} beam segment(s)…")
        for i, (p0, p1) in enumerate(import_result.beam_segments):
            try:
                sl.add_beam(seg2d(p0, p1))
                summary.beams_created += 1
            except Exception as exc:
                msg = f"  Beam #{i+1} {p0}→{p1}: FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Beams created: {summary.beams_created}")

    # ── 7  COLUMNS ───────────────────────────────────────────────────────────
    cfg_col = layer_map.get("column")
    if cfg_col and cfg_col.enabled and import_result.column_points:
        spec: ColumnSpec = cfg_col.spec
        conc = _get_concrete(concretes, spec.concrete_name)
        dc   = cad.default_column
        dc.b          = spec.b
        dc.d          = spec.d
        dc.height     = spec.height
        dc.angle      = spec.angle
        dc.below_slab = spec.below_slab
        dc.fixed_near = spec.fixed_near
        dc.fixed_far  = spec.fixed_far
        dc.compressible = spec.compressible
        dc.concrete   = conc
        dc.i_factor   = spec.i_factor
        dc.roller     = False
        dc.use_specified_LLR_parameters = False
        log(f"Adding {len(import_result.column_points)} column(s)…")
        for i, cp in enumerate(import_result.column_points):
            try:
                col = sl.add_column(Point2D(cp.x, cp.y))
                # Per-block overrides (e.g. different sizes for different block names)
                if cp.block_name and cp.block_name in spec.block_size_map:
                    ov = spec.block_size_map[cp.block_name]
                    if "b" in ov:     col.b     = ov["b"]
                    if "d" in ov:     col.d     = ov["d"]
                    if "angle" in ov: col.angle = ov["angle"]
                elif cp.rotation != 0.0:
                    # Use block rotation as column angle if no explicit override
                    col.angle = cp.rotation
                summary.columns_created += 1
            except Exception as exc:
                msg = f"  Column #{i+1} ({cp.x},{cp.y}): FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Columns created: {summary.columns_created}")

    # ── 8  LINE SUPPORTS ─────────────────────────────────────────────────────
    cfg_ls = layer_map.get("line_support")
    if cfg_ls and cfg_ls.enabled and import_result.line_support_segments:
        spec: LineSupportSpec = cfg_ls.spec
        dls = cad.default_line_support
        try:
            dls.spring_kv        = spec.spring_kv
            dls.spring_ku        = spec.spring_ku
            dls.spring_kv_factor = spec.spring_kv_factor
        except AttributeError:
            pass
        log(f"Adding {len(import_result.line_support_segments)} line support(s)…")
        for i, (p0, p1) in enumerate(import_result.line_support_segments):
            try:
                sl.add_line_support(seg2d(p0, p1))
                summary.line_supports_created += 1
            except Exception as exc:
                msg = f"  Line support #{i+1}: FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Line supports created: {summary.line_supports_created}")

    # ── 9  POINT SUPPORTS ────────────────────────────────────────────────────
    cfg_ps = layer_map.get("point_support")
    if cfg_ps and cfg_ps.enabled and import_result.point_support_points:
        spec: PointSupportSpec = cfg_ps.spec
        dps = cad.default_point_support
        try:
            dps.spring_kv        = spec.spring_kv
            dps.spring_ku        = spec.spring_ku
            dps.spring_kv_factor = spec.spring_kv_factor
        except AttributeError:
            pass
        log(f"Adding {len(import_result.point_support_points)} point support(s)…")
        for i, (x, y) in enumerate(import_result.point_support_points):
            try:
                sl.add_point_support(Point2D(x, y))
                summary.point_supports_created += 1
            except Exception as exc:
                msg = f"  Point support #{i+1} ({x},{y}): FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Point supports created: {summary.point_supports_created}")

    # ── 10  AREA SPRINGS ─────────────────────────────────────────────────────
    cfg_as = layer_map.get("area_spring")
    if cfg_as and cfg_as.enabled and import_result.area_spring_polygons:
        spec: AreaSpringSpec = cfg_as.spec
        das = cad.default_area_spring
        try:
            das.kv           = spec.kv
            das.ku           = spec.ku
            das.zero_tension = spec.zero_tension
        except AttributeError:
            pass
        log(f"Adding {len(import_result.area_spring_polygons)} area spring(s)…")
        for i, poly in enumerate(import_result.area_spring_polygons):
            try:
                sl.add_area_spring(poly2d(poly))
                summary.area_springs_created += 1
            except Exception as exc:
                msg = f"  Area spring #{i+1}: FAILED – {exc}"
                summary.errors.append(msg); log(msg)
    log(f"  Area springs created: {summary.area_springs_created}")

    # ── 11  DXF parser skips ─────────────────────────────────────────────────
    for skip in import_result.skipped:
        msg = f"  DXF skipped [{skip.etype}] handle={skip.handle} layer='{skip.layer}': {skip.reason}"
        summary.skipped.append(msg)
        log(msg)

    # ── 12  MESH ─────────────────────────────────────────────────────────────
    if mesh_after:
        if summary.slabs_created > 0:
            log("Generating mesh…")
            try:
                model.generate_mesh()
                log("  Mesh generated successfully.")
            except Exception as exc:
                msg = f"  generate_mesh() FAILED: {exc}"
                summary.errors.append(msg); log(msg)
        else:
            log("⚠  Mesh skipped – no slab areas were created.")

    # ── restore units ─────────────────────────────────────────────────────────
    try:
        units.set_units(saved_units)
        signs.set_signs(saved_signs)
    except Exception:
        pass

    log(
        f"\nBuild complete: {summary.total_objects()} object(s) created, "
        f"{len(summary.errors)} error(s), {len(summary.skipped)} DXF skip(s)."
    )
    return summary
