# DXF → RAM Concept Structural Importer v3.0

A Python tool that reads structural drawings from AutoCAD DXF files and automatically creates a complete RAM Concept model — including geometry, structural elements, materials, and loads.

## Features

### Structural Elements
| Element | DXF Entity Types | Auto-Detection |
|---------|-----------------|----------------|
| **Slab** | Closed LWPOLYLINE/POLYLINE | Multiple thickness zones via layers |
| **Beam** | LINE/POLYLINE (centerline) | Width×depth from layer name (e.g. `BEAMS 25x80`) |
| **Column (rectangular)** | LWPOLYLINE/INSERT/POINT | Auto-detects b×d from polygon shape |
| **Column (circular)** | CIRCLE | Auto-detects diameter from radius |
| **Wall** | LINE/POLYLINE (centerline) | Thickness from layer name or config |
| **Opening** | Closed LWPOLYLINE/POLYLINE | — |
| **Drop Cap** | Closed LWPOLYLINE/POLYLINE | — |
| **Drop Panel** | Closed LWPOLYLINE/POLYLINE | — |
| **Point Support** | POINT/CIRCLE | — |
| **Line Support** | LINE/POLYLINE | — |
| **Area Spring** | Closed LWPOLYLINE/POLYLINE | — |

### Load Types
| Load | DXF Entity | Properties |
|------|-----------|-----------|
| **Point Load** | POINT | Fx, Fy, Fz, Mx, My (dead + live) |
| **Line Load** | LINE/POLYLINE | Fx, Fy, Fz, Mx, My (dead + live) |
| **Area Load** | Closed LWPOLYLINE/POLYLINE | Fx, Fy, Fz, Mx, My (dead + live) |

### Key Capabilities
- **Smart layer auto-detection** — layer names containing keywords (slab, beam, column, wall, etc.) are automatically matched
- **Dimension parsing from layer names** — e.g. `GC-BEAMS 25x80` → width=0.25m, depth=0.80m
- **Column shape detection** — CIRCLE entities → circular, polyline → rectangular with auto b×d
- **Multiple instances per element type** — each DXF layer gets its own editable properties
- **Above + below slab support** — walls and columns can be continuous through the slab
- **Materials configuration** — concrete properties with code Ec option
- **GUI + CLI modes** — Tkinter GUI for interactive use, CLI for scripting/automation

---

## Prerequisites

- **Python 3.9+**
- **ezdxf** — `pip install ezdxf`
- **RAM Concept 2024+** — with the Python scripting API
- **Tkinter** — included with most Python distributions

## Installation

```bash
# Clone or download this project
cd ram_concept

# Install Python dependencies
pip install ezdxf
```

Ensure your RAM Concept installation includes the Python API. The API is typically located at:
```
C:\Program Files\Bentley\Engineering\RAM Concept\RAM Concept 2024\python
```

---

## Usage

### GUI Mode (Default)

```bash
python main.py
```

**Workflow:**
1. **Files & Settings tab** — set DXF input file, output .cpt path, RAM API folder, design code, units
2. Click **"Process DXF"** — scans layers, auto-populates element tables
3. **Structure tab** — review/edit properties for each element type (one row per matched layer)
4. **Loads tab** — configure dead/live load values for line, area, and point loads
5. **Materials tab** — set concrete and PT system properties
6. Click **"Preview"** — dry-run geometry extraction (no RAM Concept needed)
7. Click **"Generate in RAM Concept"** — full pipeline: parse DXF → create model → save .cpt

### CLI Mode

```bash
# Preview only (no RAM Concept needed)
python main.py --cli --dxf input.dxf --preview-only

# Full import
python main.py --cli --dxf input.dxf --output model.cpt \
    --api "C:/Program Files/.../python" \
    --units mm --code "ACI 318-14 (SI)" \
    --fc 45 --concrete-name "C45"
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--cli` | — | Run without GUI |
| `--dxf` | — | DXF file path (required in CLI) |
| `--output` | — | Output .cpt file path |
| `--api` | — | RAM Concept API 'python' folder |
| `--units` | `mm` | Drawing units: mm, cm, m, in, ft |
| `--code` | `ACI 318-14 (SI)` | Design code |
| `--structure` | `Elevated slab` | Structure type |
| `--fc` | `45` | Concrete f'c in MPa |
| `--concrete-name` | `45 MPa` | Concrete mix name |
| `--no-mesh` | — | Skip auto-mesh after import |
| `--gui-mode` | — | Show RAM Concept GUI (not headless) |
| `--preview-only` | — | Preview geometry only |

---

## DXF Drawing Conventions

### Layer Naming

The importer uses **keyword-based matching** — any layer whose name contains one of the keywords below is auto-detected:

| Element | Keywords |
|---------|----------|
| Slab | `slab` |
| Beam | `beam` |
| Column | `column`, `col` |
| Wall | `wall` |
| Opening | `opening`, `void` |
| Drop Cap | `drop_cap`, `dropcap`, `drop cap` |
| Drop Panel | `drop_panel`, `droppanel`, `drop panel` |
| Point Support | `point_support`, `pointsupport` |
| Line Support | `line_support`, `linesupport` |
| Area Spring | `area_spring`, `areaspring` |
| Line Load | `lineload`, `line_load`, `line load` |
| Area Load | `areaload`, `area_load`, `area load` |
| Point Load | `pointload`, `point_load`, `point load` |

**Examples:**
```
GC-SLAB EDGE 300       → slab (thickness hint: 300 in DXF units)
GC-BEAMS 25x80         → beam (width=25, depth=80 in DXF units)
GC-COLUMNS              → column
GC-Core WALL            → wall
Opening_01              → opening
GC-AreaLoad Main        → area load
```

### Dimension Hints in Layer Names

The importer parses dimensions from layer names:
- **Two dimensions:** `25x80`, `300X600` → width × depth
- **Single dimension:** trailing number → thickness or diameter

### DXF Entity Types per Element

| Element | Draw as... |
|---------|------------|
| **Slab, Opening, Drop Cap/Panel, Area Spring** | Closed LWPOLYLINE tracing the boundary |
| **Beam, Wall, Line Support** | LINE or POLYLINE along the centerline |
| **Column** | CIRCLE for circular, closed LWPOLYLINE for rectangular, or POINT for location-only |
| **Point Support, Point Load** | POINT entity at the location |
| **Line Load** | LINE or POLYLINE along the load path |
| **Area Load** | Closed LWPOLYLINE tracing the loaded area |

---

## Architecture

```
ram_concept/
├── main.py                    # Entry point (GUI + CLI)
├── config.json                # Persisted user settings
├── core/
│   ├── constants.py           # Design codes, units, element keywords
│   ├── models.py              # All dataclasses (specs, config, layers)
│   ├── geometry.py            # Shape detection + dimension parsing
│   ├── layer_parser.py        # Keyword-based layer auto-detection
│   ├── dxf_reader.py          # DXF geometry extraction
│   ├── ram_builder.py         # RAM Concept structural builder
│   └── ram_loader.py          # RAM Concept load builder
├── gui/
│   ├── app.py                 # Main Tkinter application
│   ├── theme.py               # Colour palette + ttk styling
│   ├── widgets.py             # Reusable widgets (entries, tables)
│   └── tabs/
│       ├── files_tab.py       # File paths + settings
│       ├── structure_tab.py   # Structural element tables
│       ├── loads_tab.py       # Load configuration tables
│       ├── materials_tab.py   # Concrete + PT properties
│       └── log_tab.py         # Colour-coded run log
```

### Data Flow

```
DXF File
  │
  ├─ layer_parser.py ──→ auto-detect layers → LayerInstance list
  │
  ├─ dxf_reader.py ───→ extract geometry → ImportResult
  │                      (segments, polygons, column shapes)
  │
  ├─ ram_builder.py ──→ build structural elements in RAM Concept
  │                      (slabs, beams, columns, walls, etc.)
  │
  └─ ram_loader.py ───→ apply loads to loading layers
                         (point, line, area loads)
```

---

## Supported Design Codes

- ACI 318-14 (SI)
- ACI 318-19 (SI)
- ACI 318-99 (US)
- AS 3600-2009
- AS 3600-2018
- Eurocode 2-2004
- BS 8110:1997
- CAN/CSA A23.3-04
- IS 456:2000

---

## Troubleshooting

### "Cannot import ram_concept"
Set the RAM Concept API folder to the `python` subfolder inside your RAM Concept installation directory:
```
C:\Program Files\Bentley\Engineering\RAM Concept\RAM Concept 2024\python
```

### No layers matched
- Check that your DXF layer names contain element keywords (e.g. `slab`, `beam`, `column`)
- Layer matching is **case-insensitive** — `SLAB`, `Slab`, `slab` all work
- Use the **Process DXF** button to see which layers were detected

### Column dimensions are wrong
- For circular columns: draw as CIRCLE entities (auto-detected diameter)
- For rectangular columns: draw as closed LWPOLYLINE (auto-detected b × d from bounding box)
- Fallback: dimensions come from the column spec defaults in the Structure tab

### Loads not appearing
- Ensure load layers are named with load keywords: `lineload`, `areaload`, `pointload`
- Dead and live values default to zero — edit them in the Loads tab
- RAM Concept must have Dead Loading and Live Loading layers (auto-created with new models)

---

## Future Extensions

- **PT Tendon support** — strand, duct, and anchor placement from DXF
- **Load combinations** — auto-generate from design code
- **DXF block analysis** — extract column dimensions from block definitions
- **Template support** — save/load element property templates
- **Batch import** — process multiple DXF files in sequence

---

## License

Internal tool — Bentley RAM Concept Python API required.
