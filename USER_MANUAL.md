# User Manual

DXF → RAM Concept Structural Importer v3.0

---

## 1. Overview

This tool reads structural drawings from AutoCAD DXF files and builds a complete RAM Concept model — slabs, beams, columns, walls, openings, supports, springs, and loads.

**Workflow:** DXF file → auto-detect layers → review properties → generate RAM Concept model (.cpt)

---

## 2. Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.9+ | With tkinter (included on Windows) |
| ezdxf | 1.0+ | `pip install ezdxf` |
| RAM Concept | 2024+ | With Python scripting API enabled |

The RAM Concept Python API is located at:
```
C:\Program Files\Bentley\Engineering\RAM Concept\RAM Concept 2024\python
```

---

## 3. Quick Start

```bash
cd ram_concept
python main.py
```

1. Set the DXF file path and output .cpt path
2. Click **Process DXF** — auto-detects layers and populates tables
3. Review/edit element properties in the Structure and Loads tabs
4. Click **Generate in RAM Concept**

---

## 4. DXF Layer Naming Convention

The importer matches layers by **keyword**. A layer is detected if its name contains the keyword anywhere, case-insensitive.

### 4.1 Required Keywords

| Element | Keyword(s) | Example Layer Names |
|---------|-----------|-------------------|
| Slab | `slab` | `slab`, `SLAB_01`, `Floor Slab Edge` |
| Beam | `beam` | `beam`, `BEAMS 25x80`, `Transfer Beam` |
| Column | `column` or `col` | `column`, `COLUMNS`, `Int Col` |
| Wall | `wall` | `wall`, `Core Wall`, `SHEAR_WALL` |
| Opening | `opening` or `void` | `opening`, `Slab Opening`, `void_01` |
| Recess (Step-down) | `recess` or `stepdown` or `depression` | `recess`, `step_down`, `GC-RECESS 50` |
| Drop Cap | `drop_cap` or `dropcap` or `drop cap` | `drop_cap`, `Drop Cap Zone` |
| Drop Panel | `drop_panel` or `droppanel` or `drop panel` | `drop_panel`, `Drop Panel` |
| Point Support | `point_support` or `pointsupport` | `point_support`, `PointSupport` |
| Line Support | `line_support` or `linesupport` | `line_support`, `LineSupport` |
| Area Spring | `area_spring` or `areaspring` | `area_spring`, `AreaSpring` |
| Line Load | `lineload` or `line_load` or `line load` | `lineload`, `Line_Load_DL` |
| Area Load | `areaload` or `area_load` or `area load` | `areaload`, `Area Load Live` |
| Point Load | `pointload` or `point_load` or `point load` | `pointload`, `Point_Load_01` |

### 4.2 Dimension Hints

Dimensions can be embedded in layer names. The importer parses them automatically.

| Pattern | Example | Result |
|---------|---------|--------|
| `NxN` | `BEAMS 25x80` | width=25, depth=80 (in DXF units) |
| `NXN` | `COLUMNS 400X600` | b=400, d=600 (in DXF units) |
| Trailing number | `slab 300` | thickness=300 (in DXF units) |

These are **starting values only** — you can override them in the GUI tables.

### 4.3 Multiple Layers Per Element Type

You can have multiple layers for the same element type. Each gets its own row in the property table with independent settings:

```
slab_200         → slab, thickness=200
slab_300         → slab, thickness=300
column_below     → column
column_above     → column (set above_slab=1 in table)
```

---

## 5. DXF Drawing Rules

### 5.1 How to Draw Each Element

| Element | Draw as... | Notes |
|---------|-----------|-------|
| **Slab** | Closed LWPOLYLINE | Trace the slab boundary |
| **Beam** | LINE or open POLYLINE | Draw at the beam centerline |
| **Column (rectangular)** | Closed LWPOLYLINE (4 vertices) | Draw the actual cross-section outline |
| **Column (circular)** | CIRCLE | Draw at actual diameter |
| **Column (point only)** | POINT | Dimensions from config |
| **Wall** | LINE or open POLYLINE | Draw at the wall centerline |
| **Opening** | Closed LWPOLYLINE | Trace the opening boundary |
| **Drop Cap / Panel** | Closed LWPOLYLINE | Trace the thickened zone boundary |
| **Point Support** | POINT | Location only |
| **Line Support** | LINE or open POLYLINE | Draw along the support |
| **Area Spring** | Closed LWPOLYLINE | Trace the spring zone boundary |
| **Point Load** | POINT | Location only; values set in GUI |
| **Line Load** | LINE or open POLYLINE | Draw along the load path |
| **Area Load** | Closed LWPOLYLINE | Trace the loaded area boundary |

### 5.2 Column Shape Detection

The importer auto-detects column shape from the DXF entity type:

- **CIRCLE** → circular column (diameter = 2 × radius)
- **Closed LWPOLYLINE, 4 vertices, right angles** → rectangular column (b = short side, d = long side, angle from orientation)
- **Closed LWPOLYLINE, many vertices, near-circular** → circular column (diameter from average radius)
- **POINT or INSERT** → location only; dimensions taken from the property table

### 5.3 Units

All DXF geometry must be drawn in the same units. Select the matching unit in the **Files & Settings** tab:

| Setting | DXF units | Scale to metres |
|---------|----------|----------------|
| Millimetres (mm) | 1 unit = 1 mm | ×0.001 |
| Centimetres (cm) | 1 unit = 1 cm | ×0.01 |
| Metres (m) | 1 unit = 1 m | ×1.0 |
| Inches (in) | 1 unit = 1 in | ×0.0254 |
| Feet (ft) | 1 unit = 1 ft | ×0.3048 |

---

## 6. GUI Reference

### 6.1 Tab: Files & Settings

| Field | Description |
|-------|------------|
| DXF input file | Path to the `.dxf` file |
| Output .cpt file | Path where the RAM Concept model will be saved |
| RAM Concept API folder | Path to the `python` subfolder in your RAM Concept install |
| DXF drawing units | Must match the units used in the DXF file |
| Design code | Structural design code for the model |
| Structure type | Elevated slab or Mat/Raft foundation |
| Generate mesh | Auto-generate finite element mesh after import |
| Run headless | Run RAM Concept without the GUI window |

### 6.2 Tab: Structure

Contains sub-tabs for each structural element type. Each sub-tab is an editable table with one row per matched DXF layer.

**Editing:** Double-click any cell to edit. For boolean values: `1` = true, `0` = false.

#### Slab Properties

| Property | Description | Default |
|----------|------------|---------|
| Thickness | Slab depth in metres | 0.25 |
| TOC | Top-of-concrete elevation in metres | 0.0 |
| Priority | Higher number wins at overlap | 1 |
| Axis | Reinforcement axis angle in degrees | 0.0 |
| Mesh as Slab | Whether to mesh as slab element | 1 |

#### Beam Properties

| Property | Description | Default |
|----------|------------|---------|
| Width | Beam width in metres | 0.30 |
| Thickness/Depth | Overall beam depth in metres | 0.50 |
| TOC | Top-of-concrete elevation | 0.0 |
| Priority | Priority over slab | 2 |
| Mesh as Slab | Mesh as slab element | 0 |

#### Column Properties

| Property | Description | Default |
|----------|------------|---------|
| Height | Column height in metres | 3.0 |
| Stiffness Factor | Bending stiffness multiplier | 1.0 |
| Fixed Near | Fixed at slab end | 1 |
| Fixed Far | Fixed at far end | 1 |
| Roller | Roller at far end (zero horizontal shear) | 0 |
| Specified LLR | Manually specified live load reduction | 0.0 |
| Below Slab | Column extends below slab | 1 |
| Above Slab | Column extends above slab | 0 |
| Compressible | Column is compressible | 1 |

#### Wall Properties

| Property | Description | Default |
|----------|------------|---------|
| Below Slab | Wall extends below slab | 1 |
| Above Slab | Wall extends above slab | 0 |
| Compressible | Wall is compressible | 1 |
| Height | Wall height in metres | 3.0 |
| Fixed Near | Fixed at slab end | 1 |
| Fixed Far | Fixed at far end | 1 |
| Shear Wall | Treat as shear wall | 1 |
| Thickness | Wall thickness in metres | 0.20 |
| Specified LLR | Manual live load reduction | 0.0 |

### 6.3 Tab: Loads

Sub-tabs for Line Load, Area Load, and Point Load. Each row represents one DXF layer.

| Property | Description | Format |
|----------|------------|--------|
| Elevation Dead | Height above slab for dead loads (m) | Number |
| Value Dead | Dead load force components | `Fx,Fy,Fz,Mx,My` |
| Elevation Live | Height above slab for live loads (m) | Number |
| Value Live | Live load force components | `Fx,Fy,Fz,Mx,My` |
| Live Load Type | Reducible or Unreducible | Dropdown |

**Load values format:** Comma-separated: `Fx,Fy,Fz,Mx,My`

Examples:
- Uniform dead load downward: `0,0,-5.0,0,0`
- Horizontal live load: `10.0,0,0,0,0`
- Zero load (skip): `0,0,0,0,0`

### 6.4 Tab: Materials

**Concrete properties:**

| Property | Description | Default |
|----------|------------|---------|
| Concrete Name | Label for the mix | C45 |
| fc_final (MPa) | 28-day compressive strength | 45 |
| fc_initial (MPa) | Initial compressive strength | 30 |
| Poisson's Ratio | — | 0.2 |
| Unit Mass (kg/m³) | For stiffness calculations | 2450 |
| Unit Mass for Loads (kg/m³) | For self-weight | 2500 |
| Use Code Ec | Use design code's Ec formula | Yes |

**PT System** fields are for future use.

### 6.5 Tab: Log

Colour-coded run log showing progress, warnings, and errors. Use **Clear Log** to reset and **Copy All** to copy contents to clipboard.

### 6.6 Footer Buttons

| Button | Action |
|--------|--------|
| **Process DXF** | Scans the DXF file, auto-detects layers, populates tables |
| **Preview** | Extracts geometry and shows counts (no RAM Concept needed) |
| **Generate in RAM Concept** | Full pipeline: parse → build → save .cpt |

---

## 7. Supported Design Codes

| Code | API Enum |
|------|---------|
| ACI 318-14 (SI) | ACI318_14_SI |
| ACI 318-19 (SI) | ACI318_19_SI |
| ACI 318-14 (US) | ACI318_14_US |
| ACI 318-19 (US) | ACI318_19_US |
| AS 3600-2009 | AS3600_2009 |
| AS 3600-2018 | AS3600_2018 |
| Eurocode 2-2004 | EC2_2004 |
| BS 8110:1997 | BS8110_1997 |
| CAN/CSA A23.3-04 | CSA_A23_3_04 |
| IS 456:2000 | IS456_2000 |

---

## 8. Troubleshooting

| Problem | Solution |
|---------|---------|
| "Cannot import ram_concept" | Set the API folder to `C:\...\RAM Concept 2024\python` |
| No layers matched | Layer names must contain keywords (slab, beam, column, etc.) |
| Column dimensions wrong | Draw columns as CIRCLE or closed LWPOLYLINE; or edit values in table |
| Loads not appearing | Set non-zero values in the Loads tab; both dead and live default to 0 |
| Mesh generation fails | Ensure at least one slab area exists and polygons are properly closed |
| "Concrete mix not found" | The concrete name in Material tab must match what was added to the model |
| Wrong scale | Verify the DXF drawing units match the selected unit in Files & Settings |
