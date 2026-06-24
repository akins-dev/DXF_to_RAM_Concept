"""
layer_config.py
===============
Central data-dictionary and spec dataclasses for every structural element
type that the DXF→RAM Concept importer supports.

Concept
-------
The LAYER_MAP dict maps a canonical element role (e.g. "wall", "column",
"slab", "beam", "opening", "drop_cap", "drop_panel", "point_support",
"line_support") to a LayerConfig.  Each LayerConfig holds:
  - layer   : the DXF layer name to look for  (user-editable in GUI/JSON)
  - enabled : toggle this element type on/off without removing the config
  - spec    : a dataclass that carries all default RAM Concept properties for
              that element type.  These are what the GUI's "Properties" panels
              expose for editing, and what the builder uses.

Design codes available in RAM Concept Python API
-------------------------------------------------
DesignCode.ACI318_14SI   – ACI 318-14  (SI units)
DesignCode.ACI318_19SI   – ACI 318-19  (SI units)
DesignCode.AS3600_09     – AS 3600-2009
DesignCode.AS3600_18     – AS 3600-2018
DesignCode.EC2_04SI      – Eurocode 2 2004
DesignCode.BS8110_97SI   – BS 8110:1997
DesignCode.CSA_A23_04SI  – CAN/CSA A23.3-04
DesignCode.IS456_00SI    – IS 456:2000

All coordinates / dimensions are in metres and Pascals (SI API units),
consistent with model.units.set_SI_API_units() in the builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Element spec dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SlabSpec:
    """Flat slab / plate slab / mat slab area."""
    thickness: float = 0.250        # m
    toc: float = 0.000              # top-of-concrete elevation, m
    priority: int = 1               # higher number = takes precedence at overlap
    concrete_name: str = "40 MPa"
    mesh_as_slab: bool = True       # True = standard isotropic plate
    no_torsion: bool = False
    # Reinforcement cover (clear cover, metres)
    cover_top: float = 0.025
    cover_bottom: float = 0.025


@dataclass
class WallSpec:
    """Shear wall / core wall below or above slab."""
    thickness: float = 0.200        # m
    height: float = 3.000           # m (storey height)
    below_slab: bool = True         # True = wall is below slab level
    shear_wall: bool = True
    compressible: bool = True
    concrete_name: str = "40 MPa"
    # Boundary conditions
    fixed_near: bool = False
    fixed_far: bool = False
    i_factor: float = 1.0           # moment of inertia modifier


@dataclass
class ColumnSpec:
    """Rectangular concrete column."""
    b: float = 0.400                # width, m
    d: float = 0.400                # depth, m
    height: float = 3.000           # m
    angle: float = 0.000            # degrees from X-axis
    below_slab: bool = True
    fixed_near: bool = True
    fixed_far: bool = True
    concrete_name: str = "40 MPa"
    i_factor: float = 1.0
    compressible: bool = True
    # Per-block-name overrides  {block_name: {"b":..., "d":..., "angle":...}}
    block_size_map: dict = field(default_factory=dict)


@dataclass
class BeamSpec:
    """Concrete beam (downstand or upstand)."""
    width: float = 0.300            # m
    depth: float = 0.500            # overall depth, m
    toc: float = 0.000              # top-of-concrete, m (usually same as slab)
    concrete_name: str = "40 MPa"
    mesh_as_slab: bool = False      # False = real beam FE, True = deep slab
    no_torsion: bool = False
    priority: int = 2               # higher than slab so beam wins at overlap
    below_slab: bool = False        # True for inverted / upstand beams


@dataclass
class OpeningSpec:
    """Slab opening (void in slab)."""
    # Openings carry no material properties – they just punch holes.
    # Kept as a dataclass so the builder loop is uniform.
    pass


@dataclass
class DropCapSpec:
    """Column drop-cap / punching shear cap – thicker slab area over column."""
    thickness: float = 0.400        # total slab+cap thickness, m
    toc: float = 0.000
    concrete_name: str = "40 MPa"
    priority: int = 3               # beats slab (1) and beam (2)


@dataclass
class DropPanelSpec:
    """Drop panel (large column thickening)."""
    thickness: float = 0.350
    toc: float = 0.000
    concrete_name: str = "40 MPa"
    priority: int = 2


@dataclass
class PointSupportSpec:
    """Point spring or column-top point support (for mat/raft foundations)."""
    spring_kv: float = 0.0          # kN/m, 0 = rigid
    spring_ku: float = 0.0
    spring_kv_factor: float = 1.0


@dataclass
class LineSupportSpec:
    """Line support (wall-on-soil or rigid line support)."""
    spring_kv: float = 0.0          # kN/m², 0 = rigid
    spring_ku: float = 0.0
    spring_kv_factor: float = 1.0


@dataclass
class AreaSpringSpec:
    """Soil spring (for mat/raft).  Polygon regions only."""
    kv: float = 40_000.0            # kN/m³  (40 MN/m³ typical stiff clay)
    ku: float = 0.0
    zero_tension: bool = True       # soil can't pull the slab down


# ---------------------------------------------------------------------------
# LayerConfig  – pairs a DXF layer name with an element spec
# ---------------------------------------------------------------------------

@dataclass
class LayerConfig:
    layer: str
    enabled: bool
    spec: object          # one of the *Spec dataclasses above


# ---------------------------------------------------------------------------
# Master mapping  –  edit layer names here or in the GUI / config.json
# ---------------------------------------------------------------------------

DEFAULT_LAYER_MAP: dict[str, LayerConfig] = {
    # ---------- Primary structural elements (Mesh Input layer)
    "slab": LayerConfig(
        layer="slab",
        enabled=True,
        spec=SlabSpec(),
    ),
    "wall": LayerConfig(
        layer="wall",
        enabled=True,
        spec=WallSpec(),
    ),
    "column": LayerConfig(
        layer="column",
        enabled=True,
        spec=ColumnSpec(),
    ),
    "beam": LayerConfig(
        layer="beam",
        enabled=True,
        spec=BeamSpec(),
    ),
    # ---------- Slab modifiers
    "opening": LayerConfig(
        layer="opening",
        enabled=True,
        spec=OpeningSpec(),
    ),
    "drop_cap": LayerConfig(
        layer="drop_cap",
        enabled=True,
        spec=DropCapSpec(),
    ),
    "drop_panel": LayerConfig(
        layer="drop_panel",
        enabled=True,
        spec=DropPanelSpec(),
    ),
    # ---------- Supports (useful for mat/raft foundation models)
    "point_support": LayerConfig(
        layer="point_support",
        enabled=False,
        spec=PointSupportSpec(),
    ),
    "line_support": LayerConfig(
        layer="line_support",
        enabled=False,
        spec=LineSupportSpec(),
    ),
    "area_spring": LayerConfig(
        layer="area_spring",
        enabled=False,
        spec=AreaSpringSpec(),
    ),
}


# ---------------------------------------------------------------------------
# Design code registry  –  human label -> ram_concept.model.DesignCode member
# ---------------------------------------------------------------------------

DESIGN_CODES: dict[str, str] = {
    "ACI 318-14 (SI)":   "ACI318_14SI",
    "ACI 318-19 (SI)":   "ACI318_19SI",
    "AS 3600-2009":      "AS3600_09",
    "AS 3600-2018":      "AS3600_18",
    "Eurocode 2-2004":   "EC2_04SI",
    "BS 8110:1997":      "BS8110_97SI",
    "CAN/CSA A23.3-04":  "CSA_A23_04SI",
    "IS 456:2000":       "IS456_00SI",
}

STRUCTURE_TYPES: dict[str, str] = {
    "Elevated slab":     "ELEVATED",
    "Mat / Raft foundation": "MAT",
}

# Units that the DXF might be drawn in -> scale factor to metres
UNIT_SCALES: dict[str, float] = {
    "Millimetres (mm)": 0.001,
    "Centimetres (cm)": 0.01,
    "Metres (m)":       1.0,
    "Inches (in)":      0.0254,
    "Feet (ft)":        0.3048,
    "Custom…":          1.0,        # user types their own value
}
