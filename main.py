#!/usr/bin/env python3
"""
DXF → RAM Concept Structural Importer v3.0
===========================================

Entry point for the application.

Usage
-----
  GUI mode (default):
    python main.py

  CLI mode (headless):
    python main.py --cli --dxf input.dxf --output model.cpt \\
                   --api "C:/Program Files/.../python" \\
                   --units mm --code "ACI 318-14 (SI)"

  Preview only (no RAM Concept needed):
    python main.py --cli --dxf input.dxf --preview-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def run_gui():
    """Launch the Tkinter GUI."""
    from gui.app import App

    app = App()
    app.mainloop()


def run_cli(args):
    """Run the import pipeline from the command line."""
    from core.constants import UNIT_SCALES, DESIGN_CODES, STRUCTURE_TYPES
    from core.layer_parser import parse_all_layers, create_layer_instances
    from core.dxf_reader import import_dxf, list_layers
    from core.models import ProjectConfig, ConcreteSpec

    dxf_path = args.dxf
    if not Path(dxf_path).is_file():
        print(f"ERROR: DXF file not found: {dxf_path}")
        sys.exit(1)

    # Unit scale
    unit_map = {
        "mm": "Millimetres (mm)",
        "cm": "Centimetres (cm)",
        "m": "Metres (m)",
        "in": "Inches (in)",
        "ft": "Feet (ft)",
    }
    unit_key = unit_map.get(args.units, "Millimetres (mm)")
    unit_scale = UNIT_SCALES.get(unit_key, 0.001)

    # Scan layers
    print(f"Scanning DXF: {dxf_path}")
    layer_names = list_layers(dxf_path)
    print(f"  Found {len(layer_names)} layers: {', '.join(layer_names)}")

    parsed = parse_all_layers(layer_names)
    instances = create_layer_instances(parsed, unit_scale)

    matched = [p for p in parsed if p.is_matched]
    print(f"  {len(matched)} layer(s) matched:")
    for pl in matched:
        dim_info = ""
        if pl.dimension_hint and pl.dimension_hint.dim1:
            dim_info = f"  (dims: {pl.dimension_hint.raw_match})"
        print(f"    {pl.layer_name} → {pl.role}{dim_info}")

    # Build active map
    active = {li.layer_name: li.role for li in instances if li.enabled}

    # Parse geometry
    print("\nExtracting geometry…")
    result = import_dxf(dxf_path, active, unit_scale)

    stats = {
        "Slabs": len(result.slab_polygons),
        "Beams": len(result.beam_segments),
        "Columns": len(result.column_geoms),
        "Walls": len(result.wall_segments),
        "Openings": len(result.opening_polygons),
        "Drop caps": len(result.drop_cap_polygons),
        "Drop panels": len(result.drop_panel_polygons),
        "Pt supports": len(result.point_support_points),
        "Ln supports": len(result.line_support_segments),
        "Area springs": len(result.area_spring_polygons),
        "Line loads": len(result.line_load_segments),
        "Area loads": len(result.area_load_polygons),
        "Point loads": len(result.point_load_points),
    }
    for name, count in stats.items():
        if count > 0:
            print(f"  {name}: {count}")

    # Column shape breakdown
    circulars = [c for c in result.column_geoms if c.shape.is_circular]
    rects = [c for c in result.column_geoms if not c.shape.is_circular]
    if circulars or rects:
        print(f"  Column shapes: {len(circulars)} circular, {len(rects)} rectangular")

    if result.skipped:
        print(f"\n  ⚠ {len(result.skipped)} skipped entities:")
        for s in result.skipped:
            print(f"    [{s.etype}] {s.layer}: {s.reason}")

    if args.preview_only:
        print("\n✓ Preview complete (--preview-only mode).")
        return

    # Full import
    if not args.output:
        print("ERROR: --output is required for full import.")
        sys.exit(1)

    api_path = args.api or ""
    if api_path and api_path not in sys.path:
        sys.path.insert(1, api_path)

    try:
        from ram_concept.concept import Concept
        from ram_concept.model import DesignCode, StructureType
    except ImportError as exc:
        print(f"ERROR: Cannot import ram_concept: {exc}")
        print("Set --api to the 'python' subfolder in your RAM Concept install.")
        sys.exit(1)

    # Refresh enum registries from the real API
    from core.constants import load_api_enums
    load_api_enums(api_path)

    from core.ram_builder import add_concrete_mix, build_structure, BuildSummary
    from core.ram_loader import apply_loads

    config = ProjectConfig(
        dxf_path=dxf_path,
        output_cpt_path=args.output,
        ram_api_path=api_path,
        design_code=args.code,
        structure_type=args.structure,
        unit_key=unit_key,
        concrete=ConcreteSpec(
            name=args.concrete_name,
            fc_final=args.fc,
        ),
        layer_instances=instances,
        mesh_after=not args.no_mesh,
        headless=not args.gui_mode,
    )

    print(f"\nStarting RAM Concept (headless={config.headless})…")
    concept = Concept.start_concept(headless=config.headless)
    try:
        model = concept.new_model()

        dc_str = DESIGN_CODES[config.design_code]
        st_str = STRUCTURE_TYPES[config.structure_type]

        def _safe_enum(cls, name, label):
            try:
                return getattr(cls, name)
            except AttributeError:
                members = [m for m in dir(cls) if not m.startswith("_") and m[0].isupper()]
                print(f"ERROR: {label} has no member '{name}'.")
                print(f"  Valid members: {', '.join(sorted(members))}")
                print(f"  Fix the mapping in core/constants.py")
                sys.exit(1)

        model.setup_new_model(
            _safe_enum(DesignCode, dc_str, "DesignCode"),
            _safe_enum(StructureType, st_str, "StructureType"),
        )
        print(f"  Design code: {config.design_code} → {dc_str}")

        add_concrete_mix(model, config.concrete)
        print(f"  Concrete: {config.concrete.name}")

        print("Building structure…")
        bs = build_structure(
            model, result, config, log=print, mesh_after=config.mesh_after
        )

        total_loads = (
            len(result.line_load_segments)
            + len(result.area_load_polygons)
            + len(result.point_load_points)
        )
        if total_loads > 0:
            print("Applying loads…")
            apply_loads(model, result, config, log=print)

        model.save_file(config.output_cpt_path)
        print(f"\n✓ Saved: {config.output_cpt_path}")
        print(f"  {bs.total_objects()} objects, {len(bs.errors)} errors")

    finally:
        concept.shut_down()
        print("Done.")


def main():
    parser = argparse.ArgumentParser(
        description="DXF → RAM Concept Structural Importer v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (no GUI)")
    parser.add_argument("--dxf", type=str, default="", help="Path to the DXF file")
    parser.add_argument("--output", type=str, default="", help="Output .cpt file path")
    parser.add_argument(
        "--api", type=str, default="", help="RAM Concept API 'python' folder path"
    )
    parser.add_argument(
        "--units",
        type=str,
        default="mm",
        choices=["mm", "cm", "m", "in", "ft"],
        help="DXF drawing units (default: mm)",
    )
    parser.add_argument(
        "--code",
        type=str,
        default="ACI 318-14 (SI)",
        help="Design code (default: ACI 318-14 (SI))",
    )
    parser.add_argument(
        "--structure",
        type=str,
        default="Elevated slab",
        choices=["Elevated slab", "Mat / Raft foundation"],
        help="Structure type (default: Elevated slab)",
    )
    parser.add_argument(
        "--concrete-name",
        type=str,
        default="C45",
        help="Concrete mix name (default: C45)",
    )
    parser.add_argument(
        "--fc", type=float, default=45.0, help="Concrete fc in MPa (default: 45)"
    )
    parser.add_argument("--no-mesh", action="store_true", help="Skip mesh generation")
    parser.add_argument(
        "--gui-mode", action="store_true", help="Show RAM Concept GUI (not headless)"
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Preview DXF geometry only (no RAM Concept)",
    )

    args = parser.parse_args()

    if args.cli:
        if not args.dxf:
            parser.error("--dxf is required in CLI mode")
        run_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
