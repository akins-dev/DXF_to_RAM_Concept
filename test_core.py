"""Quick smoke-test for all core modules."""
import sys
import os

# Ensure we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 1. Constants
from core.constants import DESIGN_CODES, ELEMENT_KEYWORDS, STRUCTURAL_ROLES, LOAD_ROLES
print(f"✓ constants: {len(DESIGN_CODES)} codes, {len(ELEMENT_KEYWORDS)} keywords")

# 2. Models
from core.models import (
    SlabSpec, BeamSpec, ColumnSpec, WallSpec, OpeningSpec,
    DropCapSpec, DropPanelSpec, PointSupportSpec, LineSupportSpec,
    AreaSpringSpec, LineLoadSpec, AreaLoadSpec, PointLoadSpec,
    LoadValues, ConcreteSpec, PTSystemSpec,
    LayerInstance, ProjectConfig, SPEC_FACTORY,
)
print(f"✓ models: {len(SPEC_FACTORY)} spec factories")

# Test LoadValues
lv = LoadValues.from_string("0,0,5.0,0,0")
assert lv.fz == 5.0, f"Expected fz=5.0, got {lv.fz}"
assert lv.to_string() == "0.0,0.0,5.0,0.0,0.0"
print(f"  LoadValues: {lv.to_string()}")

from core.ram_loader import _api_load_values

assert _api_load_values(lv) == (0.0, 0.0, -5000.0, 0.0, 0.0)
assert _api_load_values(LoadValues.from_string("0,0,-5.0,0,0")) == (
    0.0,
    0.0,
    -5000.0,
    0.0,
    0.0,
)

# Test LayerInstance auto-spec
li = LayerInstance(layer_name="test", role="slab")
assert isinstance(li.spec, SlabSpec)
li2 = LayerInstance(layer_name="test", role="column")
assert isinstance(li2.spec, ColumnSpec)
print(f"  LayerInstance auto-spec: slab→{type(li.spec).__name__}, col→{type(li2.spec).__name__}")

# 3. Geometry
from core.geometry import (
    parse_dimensions_from_layer_name,
    detect_shape_from_polygon,
    detect_shape_from_circle,
)

# Dimension parsing
h1 = parse_dimensions_from_layer_name("GC-BEAMS 25x80")
assert h1.dim1 == 25.0 and h1.dim2 == 80.0, f"Expected 25x80, got {h1}"
h2 = parse_dimensions_from_layer_name("GC-SLAB EDGE 300")
assert h2.dim1 == 300.0 and h2.dim2 is None
h3 = parse_dimensions_from_layer_name("GC-COLUMNS")
assert h3.dim1 is None
print(f"✓ geometry: parse dims OK (25x80→{h1.dim1}×{h1.dim2}, 300→{h2.dim1})")

# Shape detection — rectangle
rect_pts = [(0,0), (4,0), (4,3), (0,3)]
shape_r = detect_shape_from_polygon(rect_pts)
assert not shape_r.is_circular
assert abs(shape_r.width - 3.0) < 0.01 and abs(shape_r.depth - 4.0) < 0.01
print(f"  Rectangle 4x3: width={shape_r.width}, depth={shape_r.depth}")

# Shape detection — circle
shape_c = detect_shape_from_circle(5.0, 5.0, 0.3)
assert shape_c.is_circular
assert abs(shape_c.diameter - 0.6) < 0.001
print(f"  Circle r=0.3: diameter={shape_c.diameter}")

# 4. Layer parser
from core.layer_parser import detect_role, parse_all_layers, create_layer_instances

assert detect_role("GC-COLUMNS")[0] == "column"
assert detect_role("slab_01")[0] == "slab"
assert detect_role("GC-AreaLoad Main")[0] == "areaload"
assert detect_role("random_stuff") is None
print("✓ layer_parser: detect_role OK")

test_layers = ["GC-SLAB EDGE 300", "GC-BEAMS 25x80", "GC-COLUMNS", "GC-Core WALL",
                "Opening_01", "GC-AreaLoad Main", "Defpoints", "0"]
parsed = parse_all_layers(test_layers)
matched = [p for p in parsed if p.is_matched]
unmatched = [p for p in parsed if not p.is_matched]
print(f"  parse_all_layers: {len(matched)} matched, {len(unmatched)} unmatched")

instances = create_layer_instances(parsed, unit_scale=0.001)
slab_inst = [i for i in instances if i.role == "slab"]
assert len(slab_inst) == 1
assert slab_inst[0].spec.thickness == 0.3  # 300 * 0.001
print(f"  create_layer_instances: slab thickness={slab_inst[0].spec.thickness}")

beam_inst = [i for i in instances if i.role == "beam"]
assert len(beam_inst) == 1
assert beam_inst[0].spec.width == 0.025  # 25 * 0.001
assert beam_inst[0].spec.depth == 0.08   # 80 * 0.001
print(f"  Beam: width={beam_inst[0].spec.width}, depth={beam_inst[0].spec.depth}")

# 5. ProjectConfig
config = ProjectConfig()
config.layer_instances = instances
slab_li = config.enabled_instances_by_role("slab")
assert len(slab_li) == 1
print(f"✓ ProjectConfig: {len(config.layer_instances)} instances")

print("\n═══════════════════════════════════════════")
print("  ALL TESTS PASSED")
print("═══════════════════════════════════════════")
