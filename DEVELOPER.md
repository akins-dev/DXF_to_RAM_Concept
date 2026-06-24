# Developer Guide

Architecture, module reference, and contribution guidelines for the DXF → RAM Concept Importer.

---

## 1. Architecture

```
main.py                         Entry point (GUI + CLI)
  │
  ├── gui/app.py                Main Tkinter window
  │     ├── tabs/files_tab.py       File paths, design code, units
  │     ├── tabs/structure_tab.py   10 sub-tabs with editable tables
  │     ├── tabs/loads_tab.py       3 sub-tabs for load types
  │     ├── tabs/materials_tab.py   Concrete + PT config
  │     └── tabs/log_tab.py         Colour-coded run log
  │
  ├── core/layer_parser.py      Layer auto-detection + dimension parsing
  │     ├── core/constants.py       Keywords, design codes, units
  │     ├── core/geometry.py        Shape detection, dimension hints
  │     └── core/models.py          14 dataclasses (specs, config)
  │
  ├── core/dxf_reader.py        DXF geometry extraction (ezdxf)
  │     └── core/geometry.py        Column shape detection
  │
  ├── core/ram_builder.py       Structure builder (RAM Concept API)
  │     └── core/models.py
  │
  └── core/ram_loader.py        Load builder (RAM Concept API)
        └── core/models.py
```

### Dependency Rules

1. `core/` modules never import from `gui/`
2. `constants.py`, `geometry.py`, `models.py` have zero external dependencies (stdlib only)
3. `dxf_reader.py` depends on `ezdxf` only
4. `ram_builder.py` and `ram_loader.py` defer RAM Concept imports to function call time (so the module loads without RAM Concept installed)
5. GUI modules import from `core/` and `gui/theme.py` / `gui/widgets.py`

---

## 2. Module Reference

### core/constants.py

| Export | Type | Description |
|--------|------|-------------|
| `DESIGN_CODES` | `dict[str, str]` | Human label → API enum name |
| `STRUCTURE_TYPES` | `dict[str, str]` | Human label → API enum name |
| `UNIT_SCALES` | `dict[str, float]` | Unit label → metres conversion factor |
| `ELEMENT_KEYWORDS` | `dict[str, list[str]]` | Role → list of matching substrings |
| `STRUCTURAL_ROLES` | `list[str]` | Ordered list of structural element roles |
| `LOAD_ROLES` | `list[str]` | Ordered list of load roles |

### core/models.py

**Element specs** — one dataclass per element type:

| Class | Role | Key Fields |
|-------|------|-----------|
| `SlabSpec` | slab | thickness, toc, priority, axis, cover_top/bottom |
| `BeamSpec` | beam | width, depth, toc, priority, no_torsion |
| `ColumnSpec` | column | b, d, height, is_circular, angle, below/above_slab, stiffness_factor, roller |
| `WallSpec` | wall | thickness, height, below/above_slab, shear_wall, fixed_near/far |
| `OpeningSpec` | opening | priority |
| `DropCapSpec` | drop_cap | thickness, toc, priority |
| `DropPanelSpec` | drop_panel | thickness, toc, priority |
| `PointSupportSpec` | point_support | spring_kv, spring_ku |
| `LineSupportSpec` | line_support | spring_kv, spring_ku |
| `AreaSpringSpec` | area_spring | kv, ku, zero_tension |

**Load specs:**

| Class | Role | Key Fields |
|-------|------|-----------|
| `LineLoadSpec` | lineload | elevation_dead/live, value_dead/live (LoadValues), live_load_type |
| `AreaLoadSpec` | areaload | (same) |
| `PointLoadSpec` | pointload | (same) |
| `LoadValues` | — | fx, fy, fz, mx, my; parse/serialize with `from_string()`/`to_string()` |

**Materials:**

| Class | Key Fields |
|-------|-----------|
| `ConcreteSpec` | name, fc_final, fc_initial, poissons_ratio, unit_mass, use_code_Ec |
| `PTSystemSpec` | pt_name, strand/duct/anchor names, Aps, Eps, Fse/Fpy/Fpu, duct dims |

**Container types:**

| Class | Description |
|-------|------------|
| `LayerInstance` | Pairs a DXF layer name + role + spec. Auto-creates default spec from `SPEC_FACTORY`. |
| `ProjectConfig` | Complete import config: file paths, settings, materials, list of LayerInstances. |

### core/geometry.py

| Function | Input | Output |
|----------|-------|--------|
| `parse_dimensions_from_layer_name(name)` | Layer name string | `DimensionHint(dim1, dim2)` |
| `detect_shape_from_polygon(pts)` | List of (x,y) vertices | `ShapeInfo(is_circular, width, depth, angle)` |
| `detect_shape_from_circle(cx, cy, r)` | Centre + radius | `ShapeInfo(is_circular=True, diameter)` |

### core/layer_parser.py

| Function | Description |
|----------|------------|
| `detect_role(layer_name)` | Returns `(role, matched_keyword)` or `None` |
| `parse_all_layers(layer_names)` | Returns list of `ParsedLayer` (role, dimension hint, matched flag) |
| `create_layer_instances(parsed, unit_scale)` | Creates `LayerInstance` objects with dimension hints applied |

### core/dxf_reader.py

| Function | Description |
|----------|------------|
| `list_layers(dxf_path)` | Returns sorted list of all layer names in the file |
| `import_dxf(dxf_path, active_layers, unit_scale)` | Full geometry extraction → `ImportResult` |

`ImportResult` contains:
- Per-role geometry lists: `wall_segments`, `column_geoms`, `slab_polygons`, etc.
- Per-layer geometry dicts: `layer_wall_segments[layer_name]`, etc.
- `skipped` list and `available_layers`

### core/ram_builder.py

| Function | Description |
|----------|------------|
| `add_concrete_mix(model, concrete_spec)` | Adds concrete to the model |
| `build_structure(model, import_result, config, log, mesh_after)` | Builds all structural elements → `BuildSummary` |

### core/ram_loader.py

| Function | Description |
|----------|------------|
| `apply_loads(model, import_result, config, log)` | Applies all loads → `LoadSummary` |

---

## 3. Adding a New Element Type

1. **Define the spec** in `core/models.py`:
   ```python
   @dataclass
   class NewElementSpec:
       property1: float = 0.0
       property2: bool = True
   ```

2. **Register in SPEC_FACTORY** in `core/models.py`:
   ```python
   SPEC_FACTORY["new_element"] = NewElementSpec
   ```

3. **Add keywords** in `core/constants.py`:
   ```python
   ELEMENT_KEYWORDS["new_element"] = ["newelement", "new_element"]
   ```

4. **Add to the appropriate role list** in `core/constants.py`:
   ```python
   STRUCTURAL_ROLES = [..., "new_element"]  # or LOAD_ROLES
   ```

5. **Add geometry handling** in `core/dxf_reader.py`:
   - Add the role to `LINEAR_ROLES`, `POLYGON_ROLES`, or `POINT_ROLES`
   - Add corresponding fields to `ImportResult`

6. **Add build logic** in `core/ram_builder.py` or `core/ram_loader.py`

7. **Add table columns** in `gui/tabs/structure_tab.py` or `gui/tabs/loads_tab.py`:
   ```python
   NEW_ELEMENT_COLUMNS = [
       {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
       {"key": "property1", "label": "Property 1", "width": 100},
   ]
   ROLE_TABLE_DEFS["new_element"] = ("New Element", NEW_ELEMENT_COLUMNS)
   ```

---

## 4. Adding a New Design Code

1. Add to `DESIGN_CODES` in `core/constants.py`:
   ```python
   "New Code Name (SI)": "API_ENUM_NAME",
   ```

2. The API enum name must match `ram_concept.model.DesignCode.<name>`. Use RAM Concept's **Help → Scripting API** to find valid enum values.

---

## 5. RAM Concept API Notes

- **API docs**: Open RAM Concept → Help → Scripting API
- **Example scripts**: `C:\...\RAM Concept 2024\python\examples\`
- **Circular columns**: Set `b = 0`, `d = diameter`
- **Units**: Always call `model.units.set_SI_API_units()` before setting coordinates (the builder does this automatically)
- **Loading layers**: Dead Loading and Live Loading layers are auto-created with new models
- **Record Macro**: Use RAM Concept's Record Macro feature to discover undocumented API calls

---

## 6. File Map

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | ~170 | Entry point, CLI arg parsing |
| `core/constants.py` | ~80 | Static registries |
| `core/models.py` | ~280 | 14 dataclasses + ProjectConfig |
| `core/geometry.py` | ~160 | Shape detection + dimension parsing |
| `core/layer_parser.py` | ~160 | Layer auto-detection |
| `core/dxf_reader.py` | ~490 | DXF parsing (ezdxf) |
| `core/ram_builder.py` | ~350 | RAM Concept structure builder |
| `core/ram_loader.py` | ~190 | RAM Concept load builder |
| `gui/app.py` | ~540 | Main Tkinter application |
| `gui/theme.py` | ~80 | Colour palette + ttk styles |
| `gui/widgets.py` | ~240 | EditableTable + styled widgets |
| `gui/tabs/files_tab.py` | ~130 | File paths + settings tab |
| `gui/tabs/structure_tab.py` | ~300 | 10 element sub-tabs |
| `gui/tabs/loads_tab.py` | ~140 | 3 load sub-tabs |
| `gui/tabs/materials_tab.py` | ~140 | Concrete + PT tab |
| `gui/tabs/log_tab.py` | ~70 | Colour-coded log tab |
| `test_core.py` | ~100 | Core module smoke test |
