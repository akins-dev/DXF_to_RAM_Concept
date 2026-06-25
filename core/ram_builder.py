"""
ram_builder.py
==============
Consumes an ImportResult from dxf_reader and builds the full RAM Concept
structural model via the official Python scripting API.

Supported elements
------------------
  Mesh-Input layer objects:
    • Slab areas (add_slab_area) — multiple thickness zones
    • Walls (add_wall) — above & below slab
    • Columns (add_column) — circular & rectangular, above & below slab
    • Beams (add_beam) — auto-dimensioned
    • Slab openings (add_slab_opening)
    • Drop caps (add_slab_area, priority 3)
    • Drop panels (add_slab_area, priority 2)
    • Point supports (add_point_support)
    • Line supports (add_line_support)
    • Area springs (add_area_spring)

All ram_concept imports are deferred so this module loads without
RAM Concept installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from core.dxf_reader import ImportResult, ColumnGeom
from core.models import (
    LayerInstance,
    ProjectConfig,
    SlabSpec,
    BeamSpec,
    ColumnSpec,
    WallSpec,
    LineSupportSpec,
    OpeningSpec,
    PointLoadSpec,
    PointSupportSpec,
    RecessSpec,
    DropCapSpec,
    DropPanelSpec,
    AreaSpringSpec,
    ConcreteSpec,
    PTSystemSpec,
)
from core.constants import DESIGN_CODES, STRUCTURE_TYPES

# ── Summary ───────────────────────────────────────────────────────────────────


@dataclass
class BuildSummary:
    slabs_created: int = 0
    walls_created: int = 0
    columns_created: int = 0
    beams_created: int = 0
    openings_created: int = 0
    drop_caps_created: int = 0
    drop_panels_created: int = 0
    recesses_created: int = 0
    point_supports_created: int = 0
    line_supports_created: int = 0
    area_springs_created: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def total_objects(self) -> int:
        return (
            self.slabs_created
            + self.walls_created
            + self.columns_created
            + self.beams_created
            + self.openings_created
            + self.drop_caps_created
            + self.drop_panels_created
            + self.recesses_created
            + self.point_supports_created
            + self.line_supports_created
            + self.area_springs_created
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_concrete(concretes, name: str):
    """Look up a concrete mix by name. Raises on mismatch."""
    try:
        result = concretes.concrete(name)
    except Exception as exc:
        raise ValueError(
            f"Concrete mix '{name}' not found in model. "
            "Ensure add_concrete_mix() was called first."
        ) from exc

    if result is None:
        # List available concrete names for debugging
        available = [c.name for c in concretes.concretes]
        raise ValueError(
            f"Concrete mix '{name}' not found in model. "
            f"Available: {available}. "
            "Check that the concrete_name in your element spec matches "
            "the name in the Materials tab."
        )
    return result


def _polygon_to_polygon2d(Polygon2D, Point2D, pts):
    return Polygon2D([Point2D(x, y) for (x, y) in pts])


def _line_to_segment2d(LineSegment2D, Point2D, p0, p1):
    return LineSegment2D(Point2D(p0[0], p0[1]), Point2D(p1[0], p1[1]))


# ── Concrete setup ────────────────────────────────────────────────────────────


def add_concrete_mix(
    model,
    concrete_spec: ConcreteSpec,
    delete_others: bool = True,
) -> str:
    """Add a concrete mix to the model. Returns the concrete name.
    
    fc values must be in MPa (e.g. 45, not 45000000).
    """
    concretes = model.concretes
    c = concretes.add_concrete(concrete_spec.name)

    # Guard: if fc looks like Pa instead of MPa, auto-correct
    fc_final = concrete_spec.fc_final
    fc_initial = concrete_spec.fc_initial
    if fc_final > 1000:
        fc_final = fc_final / 1e6
    if fc_initial > 1000:
        fc_initial = fc_initial / 1e6

    c.fc_final = fc_final
    c.fc_initial = fc_initial
    c.poissons_ratio = concrete_spec.poissons_ratio
    c.unit_mass = concrete_spec.unit_mass
    try:
        c.unit_mass_for_loads = concrete_spec.unit_mass_for_loads
    except AttributeError:
        pass
    c.use_code_Ec = concrete_spec.use_code_Ec

    if delete_others:
        for other in list(concretes.concretes):
            if other.name != concrete_spec.name:
                try:
                    other.delete()
                except Exception:
                    pass
    return concrete_spec.name


# ── Main builder ──────────────────────────────────────────────────────────────



def _collection_item(collection, finder_name: str, adder_name: str, item_name: str):
    """Find a named RAM Concept collection item, or create it if absent."""
    finder = getattr(collection, finder_name)
    try:
        item = finder(item_name)
        if item is not None:
            return item
    except Exception:
        pass
    return getattr(collection, adder_name)(item_name)


def _enum_member(enum_class, name: str):
    try:
        return getattr(enum_class, name)
    except AttributeError as exc:
        members = [m for m in dir(enum_class) if not m.startswith("_") and m[0].isupper()]
        raise ValueError(
            f"{enum_class.__name__} has no member '{name}'. Valid members: {', '.join(sorted(members))}"
        ) from exc


def _set_attr(obj, attr: str, value, log: Callable[[str], None], label: str):
    try:
        setattr(obj, attr, value)
    except Exception as exc:
        log(f"  PT warning: could not set {label}.{attr}: {exc}")


def add_pt_system_definition(
    model,
    pt_spec: PTSystemSpec,
    log: Callable[[str], None] = print,
):
    """Create/update RAM Concept PT definition objects when PT is enabled.

    RAM Concept separates PT data into StrandMaterial, DuctSystem,
    AnchorSystem, and PTSystem. The PTSystem links the other three.
    Tendon geometry is not generated here; this only prepares the named
    definitions that tendons can use later.
    """
    if not pt_spec.use_pt_system:
        log("  PT system disabled - no PT definitions created.")
        return None

    from ram_concept.anchor_system import AnchorType
    from ram_concept.duct_system import DuctShape, DuctType, PTSystemType

    strand = None
    duct = None
    anchor = None

    if pt_spec.use_strand_material:
        strand = _collection_item(
            model.strand_materials,
            "strand_material",
            "add_strand_material",
            pt_spec.strand_name,
        )
        _set_attr(strand, "Aps", pt_spec.aps, log, pt_spec.strand_name)
        _set_attr(strand, "Eps", pt_spec.eps, log, pt_spec.strand_name)
        _set_attr(strand, "Fpy", pt_spec.fpy, log, pt_spec.strand_name)
        _set_attr(strand, "Fpu", pt_spec.fpu, log, pt_spec.strand_name)
        log(f"  PT strand material ready: {pt_spec.strand_name}")
    else:
        try:
            strand = model.strand_materials.strand_material(pt_spec.strand_name)
        except Exception:
            strand = None

    if pt_spec.use_duct_system:
        duct = _collection_item(
            model.duct_systems,
            "duct_system",
            "add_duct_system",
            pt_spec.duct_name,
        )
        _set_attr(duct, "system_type", _enum_member(PTSystemType, pt_spec.system_type), log, pt_spec.duct_name)
        _set_attr(duct, "duct_shape", _enum_member(DuctShape, pt_spec.duct_shape), log, pt_spec.duct_name)
        _set_attr(duct, "duct_type", _enum_member(DuctType, pt_spec.duct_type), log, pt_spec.duct_name)
        _set_attr(duct, "duct_width", pt_spec.duct_width, log, pt_spec.duct_name)
        _set_attr(duct, "duct_height", pt_spec.duct_height, log, pt_spec.duct_name)
        _set_attr(duct, "strands_per_duct", pt_spec.strands_per_duct, log, pt_spec.duct_name)
        _set_attr(duct, "angular_friction", pt_spec.angular_friction, log, pt_spec.duct_name)
        _set_attr(duct, "wobble_friction", pt_spec.wobble_friction, log, pt_spec.duct_name)
        log(f"  PT duct system ready: {pt_spec.duct_name}")
    else:
        try:
            duct = model.duct_systems.duct_system(pt_spec.duct_name)
        except Exception:
            duct = None

    if pt_spec.use_anchor_system:
        anchor = _collection_item(
            model.anchor_systems,
            "anchor_system",
            "add_anchor_system",
            pt_spec.anchor_name,
        )
        _set_attr(anchor, "anchor_type", _enum_member(AnchorType, pt_spec.anchor_type), log, pt_spec.anchor_name)
        _set_attr(anchor, "anchor_friction", pt_spec.anchor_friction, log, pt_spec.anchor_name)
        _set_attr(anchor, "jack_stress", pt_spec.jack_stress, log, pt_spec.anchor_name)
        _set_attr(anchor, "seating_distance", pt_spec.seating_distance, log, pt_spec.anchor_name)
        log(f"  PT anchor system ready: {pt_spec.anchor_name}")
    else:
        try:
            anchor = model.anchor_systems.anchor_system(pt_spec.anchor_name)
        except Exception:
            anchor = None

    pt = _collection_item(model.pt_systems, "pt_system", "add_pt_system", pt_spec.pt_name)
    if strand is not None:
        _set_attr(pt, "strand_material", strand, log, pt_spec.pt_name)
    elif pt_spec.use_strand_material:
        raise ValueError(f"PT strand material '{pt_spec.strand_name}' was not available.")

    if duct is not None:
        _set_attr(pt, "duct_system", duct, log, pt_spec.pt_name)
    elif pt_spec.use_duct_system:
        raise ValueError(f"PT duct system '{pt_spec.duct_name}' was not available.")

    if anchor is not None:
        _set_attr(pt, "anchor_system", anchor, log, pt_spec.pt_name)
    elif pt_spec.use_anchor_system:
        raise ValueError(f"PT anchor system '{pt_spec.anchor_name}' was not available.")

    _set_attr(pt, "Fse", pt_spec.fse, log, pt_spec.pt_name)
    _set_attr(pt, "long_term_losses", pt_spec.long_term_losses, log, pt_spec.pt_name)
    _set_attr(pt, "min_curvature_radius", pt_spec.min_curvature_radius, log, pt_spec.pt_name)
    log(f"  PT system ready: {pt_spec.pt_name}")
    return pt

def build_structure(
    model,
    import_result: ImportResult,
    config: ProjectConfig,
    log: Callable[[str], None] = print,
    mesh_after: bool = True,
) -> BuildSummary:
    """
    Populate the RAM Concept model from ImportResult geometry.

    Uses per-layer-instance properties so that each DXF layer can have
    different dimensions/settings for the same element type.
    """
    # Deferred imports
    from ram_concept.line_segment_2D import LineSegment2D
    from ram_concept.point_2D import Point2D
    from ram_concept.polygon_2D import Polygon2D

    summary = BuildSummary()
    cad = model.cad_manager
    sl = cad.structure_layer
    concretes = model.concretes

    # Save & switch to SI API units
    units = model.units
    signs = model.signs
    saved_units = units.get_units()
    saved_signs = signs.get_signs()
    units.set_SI_API_units()
    signs.set_positive_signs()

    def poly2d(pts):
        return _polygon_to_polygon2d(Polygon2D, Point2D, pts)

    def seg2d(p0, p1):
        return _line_to_segment2d(LineSegment2D, Point2D, p0, p1)

    # ── 1. SLAB AREAS ────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("slab"):
        spec: SlabSpec = li.spec
        polys = import_result.layer_slab_polygons.get(li.layer_name, [])
        if not polys:
            continue
        conc = _get_concrete(concretes, spec.concrete_name)
        da = cad.default_slab_area
        da.thickness = spec.thickness
        da.toc = spec.toc
        da.concrete = conc
        da.priority = spec.priority
        try:
            da.mesh_as_slab = spec.mesh_as_slab
        except AttributeError:
            pass
        log(f"Adding {len(polys)} slab(s) from '{li.layer_name}'…")
        for i, poly in enumerate(polys):
            try:
                sl.add_slab_area(poly2d(poly))
                summary.slabs_created += 1
            except Exception as exc:
                msg = f"  Slab #{i+1} [{li.layer_name}]: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    if summary.slabs_created == 0 and not import_result.slab_polygons:
        log("⚠  No slab polygons found – RAM Concept needs at least one slab area.")

    # ── 2. DROP PANELS ────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("drop_panel"):
        spec: DropPanelSpec = li.spec
        polys = import_result.layer_drop_panel_polygons.get(li.layer_name, [])
        if not polys:
            continue
        conc = _get_concrete(concretes, spec.concrete_name)
        da = cad.default_slab_area
        da.thickness = spec.thickness
        da.toc = spec.toc
        da.concrete = conc
        da.priority = spec.priority
        log(f"Adding {len(polys)} drop panel(s) from '{li.layer_name}'…")
        for i, poly in enumerate(polys):
            try:
                sl.add_slab_area(poly2d(poly))
                summary.drop_panels_created += 1
            except Exception as exc:
                msg = f"  Drop panel #{i+1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── 3. DROP CAPS ──────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("drop_cap"):
        spec: DropCapSpec = li.spec
        polys = import_result.layer_drop_cap_polygons.get(li.layer_name, [])
        if not polys:
            continue
        conc = _get_concrete(concretes, spec.concrete_name)
        da = cad.default_slab_area
        da.thickness = spec.thickness
        da.toc = spec.toc
        da.concrete = conc
        da.priority = spec.priority
        log(f"Adding {len(polys)} drop cap(s) from '{li.layer_name}'…")
        for i, poly in enumerate(polys):
            try:
                sl.add_slab_area(poly2d(poly))
                summary.drop_caps_created += 1
            except Exception as exc:
                msg = f"  Drop cap #{i+1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── RECESSES ──────────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("recess"):
        spec: RecessSpec = li.spec
        polys = import_result.layer_recess_polygons.get(li.layer_name, [])
        if not polys:
            continue
        conc = _get_concrete(concretes, spec.concrete_name)

        # Geometry:
        #   TOC       = -recess_depth           (step the top surface down)
        #   thickness = slab_thickness - recess_depth  (keep the soffit flush)
        recess_toc = -abs(spec.recess_depth)
        recess_thickness = spec.slab_thickness - abs(spec.recess_depth)
        if recess_thickness <= 0:
            msg = (
                f"  Recess '{li.layer_name}': recess_depth ({spec.recess_depth}m) "
                f">= slab_thickness ({spec.slab_thickness}m) — skipping."
            )
            summary.errors.append(msg)
            log(msg)
            continue

        da = cad.default_slab_area
        da.toc = recess_toc
        da.thickness = recess_thickness
        da.concrete = conc
        da.priority = spec.priority
        try:
            da.mesh_as_slab = spec.mesh_as_slab
        except AttributeError:
            pass
        log(
            f"Adding {len(polys)} recess(es) from '{li.layer_name}' "
            f"(depth={spec.recess_depth*1000:.0f}mm, "
            f"toc={recess_toc*1000:.0f}mm, "
            f"thickness={recess_thickness*1000:.0f}mm)…"
        )
        for i, poly in enumerate(polys):
            try:
                sl.add_slab_area(poly2d(poly))
                summary.recesses_created += 1
            except Exception as exc:
                msg = f"  Recess #{i+1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── 4. SLAB OPENINGS ──────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("opening"):
        polys = import_result.layer_opening_polygons.get(li.layer_name, [])
        if not polys:
            continue
        log(f"Adding {len(polys)} opening(s) from '{li.layer_name}'…")
        for i, poly in enumerate(polys):
            try:
                sl.add_slab_opening(poly2d(poly))
                summary.openings_created += 1
            except Exception as exc:
                msg = f"  Opening #{i+1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── 5. WALLS ──────────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("wall"):
        spec: WallSpec = li.spec
        segs = import_result.layer_wall_segments.get(li.layer_name, [])
        if not segs:
            continue
        conc = _get_concrete(concretes, spec.concrete_name)
        dw = cad.default_wall
        dw.thickness = spec.thickness
        dw.height = spec.height
        dw.below_slab = spec.below_slab
        dw.shear_wall = spec.shear_wall
        dw.compressible = spec.compressible
        dw.concrete = conc
        dw.fixed_near = spec.fixed_near
        dw.fixed_far = spec.fixed_far
        try:
            dw.i_factor = spec.i_factor
        except AttributeError:
            pass
        dw.use_specified_LLR_parameters = spec.use_specified_LLR
        log(f"Adding {len(segs)} wall(s) from '{li.layer_name}'…")
        for i, (p0, p1) in enumerate(segs):
            try:
                sl.add_wall(seg2d(p0, p1))
                summary.walls_created += 1
            except Exception as exc:
                msg = f"  Wall #{i+1} {p0}→{p1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

        # If above_slab is also enabled, add walls above too
        if spec.above_slab:
            dw.below_slab = False
            log(f"Adding {len(segs)} wall(s) above slab from '{li.layer_name}'…")
            for i, (p0, p1) in enumerate(segs):
                try:
                    sl.add_wall(seg2d(p0, p1))
                    summary.walls_created += 1
                except Exception as exc:
                    msg = f"  Wall above #{i+1}: FAILED – {exc}"
                    summary.errors.append(msg)
                    log(msg)

    # ── 6. BEAMS ──────────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("beam"):
        spec: BeamSpec = li.spec
        segs = import_result.layer_beam_segments.get(li.layer_name, [])
        if not segs:
            continue
        conc = _get_concrete(concretes, spec.concrete_name)
        db = cad.default_beam
        db.width = spec.width
        db.thickness = spec.depth
        db.toc = spec.toc
        db.concrete = conc
        db.priority = spec.priority
        try:
            db.mesh_as_slab = spec.mesh_as_slab
        except AttributeError:
            pass
        try:
            db.no_torsion = spec.no_torsion
        except AttributeError:
            pass
        log(f"Adding {len(segs)} beam(s) from '{li.layer_name}'…")
        for i, (p0, p1) in enumerate(segs):
            try:
                sl.add_beam(seg2d(p0, p1))
                summary.beams_created += 1
            except Exception as exc:
                msg = f"  Beam #{i+1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── 7. COLUMNS ────────────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("column"):
        spec: ColumnSpec = li.spec
        col_geoms = import_result.layer_column_geoms.get(li.layer_name, [])
        if not col_geoms:
            continue
        conc = _get_concrete(concretes, spec.concrete_name)
        dc = cad.default_column
        dc.height = spec.height
        try:
            dc.i_factor = spec.stiffness_factor
        except AttributeError:
            pass
        dc.fixed_near = spec.fixed_near
        dc.fixed_far = spec.fixed_far
        dc.compressible = spec.compressible
        dc.concrete = conc
        dc.roller = spec.roller
        dc.below_slab = spec.below_slab
        dc.use_specified_LLR_parameters = spec.use_specified_LLR
        log(f"Adding {len(col_geoms)} column(s) from '{li.layer_name}'…")
        for i, cg in enumerate(col_geoms):
            try:
                # Determine dimensions: use DXF-detected shape or spec defaults
                if cg.shape.is_circular or spec.is_circular:
                    # Circular: width=0, depth=diameter
                    diam = cg.shape.diameter if cg.shape.diameter > 0 else spec.d
                    dc.b = 0
                    dc.d = diam
                else:
                    # Rectangular: use detected dims or spec defaults
                    dc.b = cg.shape.width if cg.shape.width > 0 else spec.b
                    dc.d = cg.shape.depth if cg.shape.depth > 0 else spec.d
                dc.angle = cg.shape.angle if cg.shape.angle != 0 else spec.angle

                col = sl.add_column(Point2D(cg.x, cg.y))

                # Per-block overrides
                if cg.block_name and cg.block_name in spec.block_size_map:
                    ov = spec.block_size_map[cg.block_name]
                    if "b" in ov:
                        col.b = ov["b"]
                    if "d" in ov:
                        col.d = ov["d"]
                    if "angle" in ov:
                        col.angle = ov["angle"]
                elif cg.rotation != 0.0:
                    col.angle = cg.rotation

                summary.columns_created += 1
            except Exception as exc:
                msg = f"  Column #{i+1} ({cg.x},{cg.y}): FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

        # If above_slab is also enabled, add columns above too
        if spec.above_slab:
            dc.below_slab = False
            log(f"Adding {len(col_geoms)} column(s) above slab from '{li.layer_name}'…")
            for i, cg in enumerate(col_geoms):
                try:
                    if cg.shape.is_circular or spec.is_circular:
                        diam = cg.shape.diameter if cg.shape.diameter > 0 else spec.d
                        dc.b = 0
                        dc.d = diam
                    else:
                        dc.b = cg.shape.width if cg.shape.width > 0 else spec.b
                        dc.d = cg.shape.depth if cg.shape.depth > 0 else spec.d
                    sl.add_column(Point2D(cg.x, cg.y))
                    summary.columns_created += 1
                except Exception as exc:
                    msg = f"  Column above #{i+1}: FAILED – {exc}"
                    summary.errors.append(msg)
                    log(msg)

    # ── 8. LINE SUPPORTS ──────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("line_support"):
        spec: LineSupportSpec = li.spec
        segs = import_result.layer_line_support_segments.get(li.layer_name, [])
        if not segs:
            continue
        dls = cad.default_line_support
        try:
            dls.spring_kv = spec.spring_kv
            dls.spring_ku = spec.spring_ku
        except AttributeError:
            pass
        log(f"Adding {len(segs)} line support(s) from '{li.layer_name}'…")
        for i, (p0, p1) in enumerate(segs):
            try:
                sl.add_line_support(seg2d(p0, p1))
                summary.line_supports_created += 1
            except Exception as exc:
                msg = f"  Line support #{i+1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── 9. POINT SUPPORTS ─────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("point_support"):
        spec: PointSupportSpec = li.spec
        pts = import_result.layer_point_support_points.get(li.layer_name, [])
        if not pts:
            continue
        dps = cad.default_point_support
        try:
            dps.spring_kv = spec.spring_kv
            dps.spring_ku = spec.spring_ku
        except AttributeError:
            pass
        log(f"Adding {len(pts)} point support(s) from '{li.layer_name}'…")
        for i, (x, y) in enumerate(pts):
            try:
                sl.add_point_support(Point2D(x, y))
                summary.point_supports_created += 1
            except Exception as exc:
                msg = f"  Point support #{i+1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── 10. AREA SPRINGS ──────────────────────────────────────────────────────
    for li in config.enabled_instances_by_role("area_spring"):
        spec: AreaSpringSpec = li.spec
        polys = import_result.layer_area_spring_polygons.get(li.layer_name, [])
        if not polys:
            continue
        das = cad.default_area_spring
        try:
            das.kv = spec.kv
            das.ku = spec.ku
            das.zero_tension = spec.zero_tension
        except AttributeError:
            pass
        log(f"Adding {len(polys)} area spring(s) from '{li.layer_name}'…")
        for i, poly in enumerate(polys):
            try:
                sl.add_area_spring(poly2d(poly))
                summary.area_springs_created += 1
            except Exception as exc:
                msg = f"  Area spring #{i+1}: FAILED – {exc}"
                summary.errors.append(msg)
                log(msg)

    # ── DXF parser skips ──────────────────────────────────────────────────────
    for skip in import_result.skipped:
        msg = (
            f"  DXF skipped [{skip.etype}] handle={skip.handle} "
            f"layer='{skip.layer}': {skip.reason}"
        )
        summary.skipped.append(msg)
        log(msg)

    # ── MESH ──────────────────────────────────────────────────────────────────
    if mesh_after:
        if summary.slabs_created > 0:
            log("Generating mesh…")
            try:
                model.generate_mesh()
                log("  Mesh generated successfully.")
            except Exception as exc:
                msg = f"  generate_mesh() FAILED: {exc}"
                summary.errors.append(msg)
                log(msg)
        else:
            log("⚠  Mesh skipped – no slab areas were created.")

    # ── Restore units ─────────────────────────────────────────────────────────
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
