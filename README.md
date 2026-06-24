# DXF → RAM Concept Structural Importer

Automatically converts AutoCAD DXF drawings into RAM Concept structural models (.cpt).

## What It Does

- Reads DXF layers and auto-detects structural elements by keyword (slab, beam, column, wall, etc.)
- Extracts geometry: polygons, segments, column shapes (circular/rectangular)
- Parses dimensions from layer names (e.g. `BEAMS 25x80` → width=0.25m, depth=0.80m)
- Builds the complete RAM Concept model via the Python scripting API
- Supports 10 structural element types + 3 load types (point, line, area)

## Install

```bash
pip install ezdxf
```

Requires RAM Concept 2024+ with the Python API. Set the API path to:
```
C:\Program Files\Bentley\Engineering\RAM Concept\RAM Concept 2024\python
```

## Run

```bash
# GUI
python main.py

# CLI — preview only (no RAM Concept needed)
python main.py --cli --dxf drawing.dxf --preview-only

# CLI — full import
python main.py --cli --dxf drawing.dxf --output model.cpt --api "C:/.../python"
```

## Documentation

| Document | Contents |
|----------|---------|
| [USER_MANUAL.md](USER_MANUAL.md) | Layer naming conventions, drawing rules, GUI reference, troubleshooting |
| [DEVELOPER.md](DEVELOPER.md) | Architecture, module reference, how to extend |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Project Structure

```
ram_concept/
├── main.py              Entry point (GUI + CLI)
├── core/                Data models + logic
│   ├── constants.py       Design codes, units, keywords
│   ├── models.py          Element/load/material specs
│   ├── geometry.py        Shape detection
│   ├── layer_parser.py    Layer auto-detection
│   ├── dxf_reader.py      DXF geometry extraction
│   ├── ram_builder.py     RAM Concept structure builder
│   └── ram_loader.py      RAM Concept load builder
├── gui/                 Tkinter interface
│   ├── app.py             Main window
│   ├── theme.py           Dark colour palette
│   ├── widgets.py         Editable table widget
│   └── tabs/              Files, Structure, Loads, Materials, Log
├── USER_MANUAL.md
├── DEVELOPER.md
└── CHANGELOG.md
```

## Supported Elements

| Structural | Loads |
|-----------|-------|
| Slab, Beam, Column, Wall | Point Load |
| Opening, Drop Cap, Drop Panel | Line Load |
| Point Support, Line Support, Area Spring | Area Load |

## License

Internal tool — requires Bentley RAM Concept license.
