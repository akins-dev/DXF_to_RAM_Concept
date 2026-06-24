# DXF → RAM Concept Structural Importer  v2.0

A Python tool that reads a DXF file with standard named layers and automatically
builds the full structural model in RAM Concept via its official Python scripting
API — walls, columns, beams, slabs, openings, drop caps, drop panels, point/line
supports, and area springs, all in one click.

---

## File structure

```
dxf_to_ramconcept/
├── dxf_to_concept_gui.py     ← RUN THIS (main GUI entry point)
├── layer_config.py           ← master element-type → DXF layer mapping + spec dataclasses
├── dxf_importer.py           ← DXF parser (ezdxf only, no RAM Concept needed)
├── ram_concept_builder.py    ← RAM Concept API calls
├── config.json               ← auto-generated; stores your settings between sessions
└── README.md                 ← this file
```

---

## Supported elements

| Role | DXF Layer (default) | Entity types read |
|------|---------------------|-------------------|
| Slab | `slab` | LWPOLYLINE (closed), POLYLINE, HATCH, SPLINE, SOLID/3DFACE |
| Wall | `wall` | LINE, LWPOLYLINE, POLYLINE |
| Column | `column` | POINT, CIRCLE, INSERT (block ref) |
| Beam | `beam` | LINE, LWPOLYLINE, POLYLINE |
| Slab Opening | `opening` | LWPOLYLINE (closed), POLYLINE, HATCH |
| Drop Cap | `drop_cap` | LWPOLYLINE (closed), POLYLINE, HATCH |
| Drop Panel | `drop_panel` | LWPOLYLINE (closed), POLYLINE, HATCH |
| Point Support | `point_support` | POINT, CIRCLE, INSERT |
| Line Support | `line_support` | LINE, LWPOLYLINE, POLYLINE |
| Area Spring | `area_spring` | LWPOLYLINE (closed), POLYLINE, HATCH |

All layer names are fully configurable in the **Layer Mapping** tab.  
Point supports and area springs are disabled by default (useful for mat/raft).

---

## DXF layer conventions

Draw each element on the matching layer.  You can use any names — just change
them in the GUI.  Suggested names (defaults):

```
slab          → closed polygons of slab boundary (one per slab region)
wall          → centrelines as LINE or POLYLINE
column        → POINT, CIRCLE, or INSERT block at the column centroid
beam          → centrelines as LINE or POLYLINE
opening       → closed polygons of voids
drop_cap      → closed polygons (the column cap region only)
drop_panel    → closed polygons (the wider panel region)
point_support → POINT / CIRCLE (raft column positions)
line_support  → LINE / POLYLINE (raft wall positions)
area_spring   → closed polygons (soil zones with spring stiffnesses)
```

**Columns from INSERT blocks** — the block insertion point is used as the column
centroid.  The block's graphical content is NOT modelled; it is only used to
locate the column.  To assign different sizes to different block types, populate
`ColumnSpec.block_size_map` in `layer_config.py`:

```python
ColumnSpec(
    b=0.4, d=0.4, ...
    block_size_map={
        "COL400x400": {"b": 0.40, "d": 0.40, "angle": 0},
        "COL600x300": {"b": 0.60, "d": 0.30, "angle": 0},
        "COL600x300_ROT45": {"b": 0.60, "d": 0.30, "angle": 45},
    }
)
```

---

## Setup

### 1  Install Python dependencies
On the machine where RAM Concept is installed and licensed:
```
pip install ezdxf
```
Python 3.8+ is required (Bentley's API requires 3.8; tested through 3.11).

### 2  Find the RAM Concept Python API folder
Typically:
```
C:\Program Files\Bentley\RAM Concept CONNECT Edition\python
```
The exact path varies with version.  You can also check **Help → Scripting API**
inside RAM Concept to confirm the location.

### 3  Run the GUI
```
python dxf_to_concept_gui.py
```

---

## Using the GUI

### Files & Units tab
- **DXF input file** — your source drawing.
- **Output .cpt file** — where the RAM Concept model will be saved.
- **RAM Concept API folder** — point to the `python` folder in your RAM Concept
  install.  Leave blank if `ram_concept` is already importable (e.g. added to
  `PYTHONPATH`).
- **DXF drawing units** — choose the unit your CAD file was drawn in.
  The importer converts to metres internally.
- **Design code** — ACI 318-14/19, AS 3600, EC2, BS 8110, CSA, IS 456.
- **Structure type** — Elevated slab or Mat/Raft foundation.
- **f'c** — characteristic compressive strength for the single global concrete
  mix (one mix is used for all elements in this version).
- **Generate mesh** — ticked by default; untick if you want to inspect geometry
  before meshing in RAM Concept.
- **Headless** — run RAM Concept without its GUI (faster, uses same license).

### Layer Mapping tab
One row per element type.  Tick the checkbox to enable; type the exact DXF
layer name.  Click **Scan Layers** in the toolbar to colour-code each row:
- 🟢 Green = layer found in the DXF file
- 🔴 Red = layer name not found (check spelling/case)

### Element Properties tab
Set default sizes for each element type.  Values are in your chosen drawing
unit (mm, m, ft, etc.) and are converted internally.

Key notes:
- **Slab priority** overrides at overlapping regions.  Slab=1, Drop panel=2,
  Drop cap=3 is the recommended ordering.
- **Beam depth** is the *total* member depth (including slab thickness for
  downstand beams in RAM Concept's convention).
- **No torsion** on beams is recommended for band beams to avoid
  over-estimated torsional stiffness adjacent to thinner slabs.
- **Column angle** is measured in degrees from the X-axis.  If your INSERT
  blocks are rotated, the rotation is read automatically and used as the angle
  unless you have an explicit block_size_map entry for that block.

### Toolbar actions
| Button | What it does |
|--------|--------------|
| **Scan Layers** | Reads the DXF, colour-codes the Layer Mapping rows |
| **Preview DXF** | Runs the parser only — no RAM Concept needed.  Shows counts and skipped entity warnings. |
| **▶ Run Import** | Full pipeline: parse DXF → start RAM Concept → add concrete → build all elements → mesh → save .cpt |
| **Save Config** | Writes all current settings to `config.json` |

---

## Design codes available

| Label in GUI | RAM Concept API constant |
|---|---|
| ACI 318-14 (SI) | `DesignCode.ACI318_14SI` |
| ACI 318-19 (SI) | `DesignCode.ACI318_19SI` |
| AS 3600-2009 | `DesignCode.AS3600_09` |
| AS 3600-2018 | `DesignCode.AS3600_18` |
| Eurocode 2-2004 | `DesignCode.EC2_04SI` |
| BS 8110:1997 | `DesignCode.BS8110_97SI` |
| CAN/CSA A23.3-04 | `DesignCode.CSA_A23_04SI` |
| IS 456:2000 | `DesignCode.IS456_00SI` |

---

## What this does NOT do (natural next steps)

- **Tendon layout** — add a `tendon` layer and extend the builder to call
  `structure_layer.add_tendon(...)`.  The RAM Concept Python API supports full
  tendon geometry and profile points.
- **Loads** — surface loads, line loads, and point loads are not imported.
  Extend with an `SDL` (superimposed dead) and `LL` (live load) layer approach,
  calling `loading_layer.add_area_load(...)`.
- **Multiple concrete mixes** — currently one global mix.  Add a per-layer
  concrete name field to each spec and call `concretes.add_concrete()` for each.
- **Per-column rotation from block geometry** — the block's rectangle geometry
  is not reverse-engineered; only `e.dxf.rotation` (INSERT rotation angle) and
  `block_size_map` are used.
- **ISM / Revit round-trip** — RAM Concept supports ISM; exporting back through
  ISM after modelling is outside the scope of this tool.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ImportError: No module named 'ram_concept'` | API path wrong or not set | Set "RAM Concept API folder" to the `python` subfolder of your RAM Concept install |
| Nothing found in preview | Layer names don't match | Use **Scan Layers** to see actual layer names, then update the Layer Mapping tab |
| RAM Concept error "No areas to mesh" | No slab polygons loaded | Draw your slab outline as a closed LWPOLYLINE on the `slab` layer |
| Columns at wrong location | DXF INSERT has an offset property | Update ezdxf to ≥ 0.18 which handles INSERT offset correctly |
| `ValueError: Concrete mix '40 MPa' not found` | Concrete name mismatch | Ensure `concrete_name` in Element Properties matches exactly what was added via `add_concrete_mix()` |
| License error when running headless | License not available | Check your Bentley SELECT license; running headless still consumes a RAM Concept or RAM Concept PT seat |

---

## Acknowledgements

Built on the official Bentley RAM Concept Python scripting API (shipped with
RAM Concept CONNECT Edition V8+).  DXF reading via the open-source
[ezdxf](https://ezdxf.readthedocs.io/) library.  Reference patterns from
Bentley's `add_structure.py`, `add_materials.py`, and `main.py` walkthrough
samples, plus community work at
[github.com/danielogg92/RamConcept-API-Python](https://github.com/danielogg92/RamConcept-API-Python)
and the Eng-Tips RAM Concept scripting thread.
