# Changelog

All notable changes to the DXF → RAM Concept Importer are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [3.0.1] — 2026-06-24

### Fixed
- **Design code enum names** — fixed `BS8110_97SI` → `BS8110_1997` and other mismatched enum names

### Changed
- **Dynamic API discovery** — `DesignCode` and `StructureType` enums are now introspected from the actual RAM Concept API at runtime via `core/api_discovery.py`. Hardcoded values are only used as a fallback when the API is not available.
- **Dropdown auto-refresh** — design code and structure type dropdowns update automatically when the API folder is set
- **Safe enum lookup** — if an enum name is wrong, the error message lists all valid members

---

## [3.0.0] — 2026-06-24

### Added
- **Modular architecture** — split into `core/` (data + logic) and `gui/` (interface) packages
- **Smart layer auto-detection** — keyword-based matching from DXF layer names
- **Dimension parsing from layer names** — e.g. `BEAMS 25x80` auto-sets width=25, depth=80
- **Column shape detection** — CIRCLE → circular, closed POLYLINE → rectangular with auto b×d
- **Load support** — point loads, line loads, area loads (dead + live with Fx,Fy,Fz,Mx,My)
- **Multi-instance layers** — multiple DXF layers can map to the same element type with different properties
- **Above + below slab** — walls and columns can be continuous through the slab
- **Materials tab** — concrete properties (fc, Ec, Poisson, unit mass) + PT system fields
- **CLI mode** — `python main.py --cli --dxf file.dxf --preview-only`
- **Editable property tables** — double-click cells in Structure/Loads tabs to edit
- **Per-layer geometry tracking** — each DXF layer's geometry is tracked independently
- **Smoke test** — `test_core.py` validates core modules without ezdxf or RAM Concept

### Changed
- Entry point moved from `dxf_to_concept_gui.py` to `main.py`
- Data models moved from `layer_config.py` to `core/models.py` (14 dataclasses)
- DXF reader moved from `dxf_importer.py` to `core/dxf_reader.py` (expanded entity support)
- RAM builder moved from `ram_concept_builder.py` to `core/ram_builder.py` + `core/ram_loader.py`
- GUI rebuilt from single file to `gui/app.py` + 5 tab modules
- Config format updated (old `config.json` is not compatible)

### Removed
- Monolithic single-file architecture
- Hardcoded layer name fields (replaced by auto-detection tables)

---

## [2.0.0] — 2026-06-20

### Added
- Tkinter GUI with tabbed interface (Geometry, Properties, Run Log)
- Config persistence via `config.json`
- Preview mode (DXF scan without RAM Concept)
- Drop cap and drop panel support
- Point support, line support, area spring support
- Design code selection dropdown
- Unit scale selection (mm, cm, m, in, ft)

---

## [1.0.0] — 2026-06-15

### Added
- Initial release
- DXF parsing for slabs, walls, columns, beams, openings
- RAM Concept model generation via Python API
- Basic concrete material setup
