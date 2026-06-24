"""
models.py
=========
Dataclasses for every structural element type, load type, and material
that the DXF → RAM Concept importer supports.

Each element type has:
  - A *Spec dataclass with all RAM Concept properties
  - Support for multiple DXF layers mapping to the same type (LayerInstance)

All dimensions are stored in the DXF's native units and converted to
metres at build time via the unit_scale factor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════


class ColumnShape(Enum):
    RECTANGULAR = "rectangular"
    CIRCULAR = "circular"


class LiveLoadType(Enum):
    UNREDUCIBLE = "Unreducible"
    REDUCIBLE = "Reducible"


# ═══════════════════════════════════════════════════════════════════════════════
# Structural element specs
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SlabSpec:
    """Flat slab / plate slab / mat slab area."""

    thickness: float = 0.250  # m
    toc: float = 0.0  # top-of-concrete elevation, m
    priority: int = 1  # higher number wins at overlap
    mesh_as_slab: bool = True
    axis: float = 0.0  # reinforcement axis angle (degrees)
    concrete_name: str = "C45"
    no_torsion: bool = False
    cover_top: float = 0.025  # m
    cover_bottom: float = 0.025  # m


@dataclass
class BeamSpec:
    """Concrete beam (downstand or upstand)."""

    width: float = 0.300  # m (can be auto-parsed from layer name)
    depth: float = 0.500  # m — overall depth (thickness in ref tool)
    toc: float = 0.0
    priority: int = 2
    mesh_as_slab: bool = False
    concrete_name: str = "C45"
    no_torsion: bool = False


@dataclass
class ColumnSpec:
    """Concrete column — rectangular or circular."""

    b: float = 0.400  # width, m (0 for circular → d is diameter)
    d: float = 0.400  # depth/diameter, m
    height: float = 3.0  # m
    stiffness_factor: float = 1.0  # bending stiffness factor
    angle: float = 0.0  # degrees from X-axis
    is_circular: bool = False  # auto-detected from DXF geometry
    # Boundary conditions
    fixed_near: bool = True
    fixed_far: bool = True
    roller: bool = False
    # Support position
    below_slab: bool = True
    above_slab: bool = False  # NEW: continuous columns
    compressible: bool = True
    # LLR
    use_specified_LLR: bool = False
    specified_LLR: float = 0.0
    # Material
    concrete_name: str = "C45"
    i_factor: float = 1.0
    # Per-block-name overrides {block_name: {"b":..., "d":..., "angle":...}}
    block_size_map: dict = field(default_factory=dict)


@dataclass
class WallSpec:
    """Shear wall / core wall."""

    thickness: float = 0.200  # m
    height: float = 3.0  # m
    # Support position
    below_slab: bool = True
    above_slab: bool = False  # NEW: continuous walls
    compressible: bool = True
    shear_wall: bool = True
    # Boundary conditions
    fixed_near: bool = True
    fixed_far: bool = True
    # LLR
    use_specified_LLR: bool = False
    specified_LLR: float = 0.0
    # Material
    concrete_name: str = "C45"
    i_factor: float = 1.0


@dataclass
class OpeningSpec:
    """Slab opening (void in slab)."""

    priority: int = 100


@dataclass
class RecessSpec:
    """Slab recess (step-down) — a depressed slab area.

    Modeled as a slab area with negative TOC and adjusted thickness.
    The recess_depth is the vertical drop from the main slab surface.
    When thickness is 0, the builder auto-calculates it to keep the soffit flat.
    """

    recess_depth: float = 0.050  # m (50mm default step-down)
    thickness: float = 0.0  # m (0 = auto: main_slab_thickness - recess_depth)
    priority: int = 5  # must be higher than main slab to override
    concrete_name: str = "C45"
    mesh_as_slab: bool = True


@dataclass
class DropCapSpec:
    """Column drop-cap — thicker slab area over column."""

    thickness: float = 0.400
    toc: float = 0.0
    priority: int = 3
    concrete_name: str = "C45"


@dataclass
class DropPanelSpec:
    """Drop panel — large column thickening."""

    thickness: float = 0.350
    toc: float = 0.0
    priority: int = 2
    concrete_name: str = "C45"


@dataclass
class PointSupportSpec:
    """Point spring or column-top support (mat/raft)."""

    spring_kv: float = 0.0  # kN/m, 0 = rigid
    spring_ku: float = 0.0
    spring_kv_factor: float = 1.0


@dataclass
class LineSupportSpec:
    """Line support (wall-on-soil or rigid line support)."""

    spring_kv: float = 0.0  # kN/m², 0 = rigid
    spring_ku: float = 0.0
    spring_kv_factor: float = 1.0


@dataclass
class AreaSpringSpec:
    """Soil spring (mat/raft). Polygon regions only."""

    kv: float = 40_000.0  # kN/m³
    ku: float = 0.0
    zero_tension: bool = True


# ═══════════════════════════════════════════════════════════════════════════════
# Load specs  (NEW — line load, area load, point load)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class LoadValues:
    """Force components for a single load case (dead or live).

    Format matches the reference tool: Fx, Fy, Fz, Mx, My
    """

    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0

    def to_tuple(self) -> tuple[float, ...]:
        return (self.fx, self.fy, self.fz, self.mx, self.my)

    @classmethod
    def from_string(cls, s: str) -> "LoadValues":
        """Parse '0,0,0,0,0' format."""
        parts = [float(x.strip()) for x in s.split(",")]
        while len(parts) < 5:
            parts.append(0.0)
        return cls(*parts[:5])

    def to_string(self) -> str:
        return f"{self.fx},{self.fy},{self.fz},{self.mx},{self.my}"


@dataclass
class LineLoadSpec:
    """Line load applied along a line/polyline."""

    elevation_dead: float = 0.0
    value_dead: LoadValues = field(default_factory=LoadValues)
    elevation_live: float = 0.0
    value_live: LoadValues = field(default_factory=LoadValues)
    live_load_type: str = "Unreducible"


@dataclass
class AreaLoadSpec:
    """Area load applied over a closed polygon."""

    elevation_dead: float = 0.0
    value_dead: LoadValues = field(default_factory=LoadValues)
    elevation_live: float = 0.0
    value_live: LoadValues = field(default_factory=LoadValues)
    live_load_type: str = "Unreducible"


@dataclass
class PointLoadSpec:
    """Point load applied at a point."""

    elevation_dead: float = 0.0
    value_dead: LoadValues = field(default_factory=LoadValues)
    elevation_live: float = 0.0
    value_live: LoadValues = field(default_factory=LoadValues)
    live_load_type: str = "Unreducible"


# ═══════════════════════════════════════════════════════════════════════════════
# Materials
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ConcreteSpec:
    """Concrete material definition. All stress values in MPa."""

    name: str = "C45"
    fc_final: float = 45.0  # MPa
    fc_initial: float = 30.0  # MPa
    poissons_ratio: float = 0.2
    unit_mass: float = 2450.0  # kg/m³
    unit_mass_for_loads: float = 2500.0
    use_code_Ec: bool = True


@dataclass
class PTSystemSpec:
    """Post-tensioning system definition (future extension).
    
    Stress values in MPa, areas in m², lengths in m.
    """

    pt_name: str = "13mm Bonded"
    strand_name: str = "13mm Strand"
    duct_name: str = "4s Flat"
    anchor_name: str = "FA Multi"
    aps: float = 100e-6  # m²
    eps: float = 195_000.0  # MPa
    fse: float = 1_100.0  # MPa
    fpy: float = 1_564.0  # MPa
    fpu: float = 1_840.0  # MPa
    duct_width: float = 70e-3  # m
    duct_height: float = 35e-3  # m
    strands_per_duct: int = 4
    min_curvature_radius: float = 2.0  # m
    anchor_friction: float = 0.02
    angular_friction: float = 0.2
    jack_stress: float = 1_564.0  # MPa
    seating_distance: float = 6e-3  # m
    long_term_losses: float = 150.0  # MPa
    wobble_friction: float = 0.005
    system_type: str = "BONDED"  # BONDED or UNBONDED
    duct_shape: str = "FLAT"  # FLAT or ROUND
    duct_type: str = "CORRUGATED_STEEL"
    anchor_type: str = "FLAT_MULTI_PLANE"


# ═══════════════════════════════════════════════════════════════════════════════
# Layer Instance — one DXF layer mapped to one element type with specific props
# ═══════════════════════════════════════════════════════════════════════════════

# Factory map: role → default spec class
SPEC_FACTORY: dict[str, type] = {
    "slab": SlabSpec,
    "beam": BeamSpec,
    "column": ColumnSpec,
    "wall": WallSpec,
    "opening": OpeningSpec,
    "drop_cap": DropCapSpec,
    "drop_panel": DropPanelSpec,
    "point_support": PointSupportSpec,
    "line_support": LineSupportSpec,
    "area_spring": AreaSpringSpec,
    "recess": RecessSpec,
    "lineload": LineLoadSpec,
    "areaload": AreaLoadSpec,
    "pointload": PointLoadSpec,
}


@dataclass
class LayerInstance:
    """One DXF layer mapped to an element role with its own properties.

    A single role (e.g. 'slab') can have multiple LayerInstances, one for
    each DXF layer that matches (e.g. 'GC-SLAB EDGE 300', 'GC-SLAB EDGE 600').
    """

    layer_name: str  # DXF layer name (exact match)
    role: str  # canonical element role
    enabled: bool = True
    spec: object = None  # one of the *Spec dataclasses

    def __post_init__(self):
        if self.spec is None:
            factory = SPEC_FACTORY.get(self.role)
            if factory:
                self.spec = factory()


@dataclass
class ProjectConfig:
    """Complete project configuration for a DXF → RAM Concept import."""

    # File paths
    dxf_path: str = ""
    output_cpt_path: str = ""
    ram_api_path: str = ""
    # Settings
    design_code: str = "ACI 318-14 (SI)"
    structure_type: str = "Elevated slab"
    unit_key: str = "Metres (m)"
    unit_scale_custom: float = 1.0
    # Materials
    concrete: ConcreteSpec = field(default_factory=ConcreteSpec)
    pt_system: PTSystemSpec = field(default_factory=PTSystemSpec)
    # Layer instances (one list per element type)
    layer_instances: list[LayerInstance] = field(default_factory=list)
    # Options
    mesh_after: bool = True
    headless: bool = True

    def instances_by_role(self, role: str) -> list[LayerInstance]:
        """Return all layer instances for a given role."""
        return [li for li in self.layer_instances if li.role == role]

    def enabled_instances_by_role(self, role: str) -> list[LayerInstance]:
        """Return only enabled layer instances for a given role."""
        return [li for li in self.layer_instances if li.role == role and li.enabled]
