"""
app.py
======
Main Tkinter application for the DXF → RAM Concept Importer v3.0.
Orchestrates the tabbed interface, config persistence, DXF scanning,
and the full import pipeline.
"""

from __future__ import annotations

import json
import sys
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

from gui.theme import (
    C_BG,
    C_PANEL,
    C_TEXT,
    C_ACCENT,
    C_ACCENT2,
    C_MUTED,
    configure_ttk_style,
)
from gui.widgets import styled_btn
from gui.tabs.files_tab import FilesTab
from gui.tabs.structure_tab import StructureTab
from gui.tabs.loads_tab import LoadsTab
from gui.tabs.materials_tab import MaterialsTab
from gui.tabs.log_tab import LogTab

from core.constants import UNIT_SCALES, DESIGN_CODES, STRUCTURE_TYPES
from core.models import (
    ProjectConfig,
    LayerInstance,
    ConcreteSpec,
    PTSystemSpec,
)
from core.layer_parser import parse_all_layers, create_layer_instances
from core.dxf_reader import import_dxf, list_layers, ImportResult

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


class App(tk.Tk):
    """DXF → RAM Concept Importer v3.0 — Main Window."""

    WIDTH = 1080
    HEIGHT = 720

    def __init__(self):
        super().__init__()
        self.title("DXF → RAM Concept Importer v3.0")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(900, 600)
        self.configure(bg=C_BG)

        # ── Variables ─────────────────────────────────────────────────────────
        self._init_vars()

        # ── Style ─────────────────────────────────────────────────────────────
        style = ttk.Style(self)
        configure_ttk_style(style)

        # ── Layout ────────────────────────────────────────────────────────────
        self._build_header()
        self._build_notebook()
        self._build_footer()

        # ── Load config ───────────────────────────────────────────────────────
        self._load_config()

        # ── State ─────────────────────────────────────────────────────────────
        self._import_result: ImportResult | None = None
        self._layer_instances: list[LayerInstance] = []

    # ══════════════════════════════════════════════════════════════════════════
    # Init variables
    # ══════════════════════════════════════════════════════════════════════════

    def _init_vars(self):
        # Files
        self.v_dxf = tk.StringVar(value="")
        self.v_output = tk.StringVar(value="")
        self.v_api_path = tk.StringVar(value="")
        # Settings
        self.v_unit_key = tk.StringVar(value="Millimetres (mm)")
        self.v_unit_custom = tk.StringVar(value="1.0")
        self.v_design_code = tk.StringVar(value="ACI 318-14 (SI)")
        self.v_struct_type = tk.StringVar(value="Elevated slab")
        self.v_mesh_after = tk.BooleanVar(value=True)
        self.v_headless = tk.BooleanVar(value=True)
        # Concrete
        self.v_conc_name = tk.StringVar(value="45 MPa")
        self.v_fc_final = tk.StringVar(value="45e6")
        self.v_fc_initial = tk.StringVar(value="30e6")
        self.v_poisson = tk.StringVar(value="0.2")
        self.v_unit_mass = tk.StringVar(value="2450")
        self.v_unit_mass_loads = tk.StringVar(value="2500")
        self.v_use_code_ec = tk.BooleanVar(value=True)
        # PT System
        self.v_pt_name = tk.StringVar(value="13mm Bonded")
        self.v_pt_strand = tk.StringVar(value="13mm Strand")
        self.v_pt_duct = tk.StringVar(value="4s Flat")
        self.v_pt_anchor = tk.StringVar(value="FA Multi")
        self.v_pt_aps = tk.StringVar(value="100e-6")
        self.v_pt_eps = tk.StringVar(value="195000e6")
        self.v_pt_fse = tk.StringVar(value="1100e6")
        self.v_pt_fpy = tk.StringVar(value="1564e6")
        self.v_pt_fpu = tk.StringVar(value="1840e6")
        self.v_pt_duct_w = tk.StringVar(value="70e-3")
        self.v_pt_duct_h = tk.StringVar(value="35e-3")
        self.v_pt_strands = tk.StringVar(value="4")
        self.v_pt_sys_type = tk.StringVar(value="BONDED")
        self.v_pt_duct_shape = tk.StringVar(value="FLAT")
        self.v_pt_duct_type = tk.StringVar(value="CORRUGATED_STEEL")
        self.v_pt_anchor_type = tk.StringVar(value="FLAT_MULTI_PLANE")

    # ══════════════════════════════════════════════════════════════════════════
    # Layout
    # ══════════════════════════════════════════════════════════════════════════

    def _build_header(self):
        hdr = tk.Frame(self, bg=C_BG, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr,
            text="DXF → RAM Concept",
            bg=C_BG,
            fg=C_ACCENT2,
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=16)
        tk.Label(
            hdr,
            text="v3.0 — Structural Importer",
            bg=C_BG,
            fg=C_MUTED,
            font=("Segoe UI", 10),
        ).pack(side="left")

    def _build_notebook(self):
        self._nb = ttk.Notebook(self, style="Dark.TNotebook")
        self._nb.pack(fill="both", expand=True, padx=8, pady=4)

        self.files_tab = FilesTab(self._nb, self)
        self.structure_tab = StructureTab(self._nb, self)
        self.loads_tab = LoadsTab(self._nb, self)
        self.materials_tab = MaterialsTab(self._nb, self)
        self.log_tab = LogTab(self._nb, self)

        self._nb.add(self.files_tab, text="  Files & Settings  ")
        self._nb.add(self.structure_tab, text="  Structure  ")
        self._nb.add(self.loads_tab, text="  Loads  ")
        self._nb.add(self.materials_tab, text="  Materials  ")
        self._nb.add(self.log_tab, text="  Log  ")

    def _build_footer(self):
        ftr = tk.Frame(self, bg=C_BG, height=50)
        ftr.pack(fill="x")
        ftr.pack_propagate(False)

        styled_btn(ftr, "  ⟳ Process DXF  ", self._on_process_dxf, accent=True).pack(
            side="left", padx=16, pady=10
        )
        styled_btn(ftr, "  ▷ Preview  ", self._on_preview).pack(
            side="left", padx=4, pady=10
        )
        styled_btn(
            ftr, "  ▶ Generate in RAM Concept  ", self._on_run, accent=True
        ).pack(side="right", padx=16, pady=10)

    # ══════════════════════════════════════════════════════════════════════════
    # Log helper
    # ══════════════════════════════════════════════════════════════════════════

    def _log(self, msg: str, level: str = "NORMAL"):
        """Thread-safe log to the log tab."""
        self.after(0, lambda: self.log_tab.append(msg, level))

    # ══════════════════════════════════════════════════════════════════════════
    # Config persistence
    # ══════════════════════════════════════════════════════════════════════════

    def _load_config(self):
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text("utf-8"))
            for key, var in self._var_map().items():
                if key in data:
                    var.set(data[key])
        except Exception:
            pass

    def _save_config(self):
        data = {k: v.get() for k, v in self._var_map().items()}
        try:
            CONFIG_FILE.write_text(json.dumps(data, indent=2), "utf-8")
        except Exception:
            pass

    def _var_map(self) -> dict:
        return {
            "dxf_path": self.v_dxf,
            "output_cpt_path": self.v_output,
            "ram_api_path": self.v_api_path,
            "unit_key": self.v_unit_key,
            "unit_scale_custom": self.v_unit_custom,
            "design_code": self.v_design_code,
            "structure_type": self.v_struct_type,
            "mesh_after": self.v_mesh_after,
            "headless": self.v_headless,
            "concrete_name": self.v_conc_name,
            "fc_final": self.v_fc_final,
            "fc_initial": self.v_fc_initial,
            "poisson": self.v_poisson,
            "unit_mass": self.v_unit_mass,
            "unit_mass_loads": self.v_unit_mass_loads,
            "use_code_ec": self.v_use_code_ec,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Actions
    # ══════════════════════════════════════════════════════════════════════════

    def _get_unit_scale(self) -> float:
        key = self.v_unit_key.get()
        if key == "Custom…":
            try:
                return float(self.v_unit_custom.get())
            except ValueError:
                return 1.0
        return UNIT_SCALES.get(key, 1.0)

    def _on_process_dxf(self):
        """Scan the DXF file, auto-detect layers, and populate tables."""
        dxf_path = self.v_dxf.get().strip()
        if not dxf_path or not Path(dxf_path).is_file():
            messagebox.showerror("No DXF", "Select a valid DXF file first.")
            return

        self._nb.select(4)  # switch to log tab
        self._log("--- Processing DXF layers ---", "INFO")

        try:
            layer_names = list_layers(dxf_path)
        except Exception as exc:
            self._log(f"DXF read error: {exc}", "ERROR")
            messagebox.showerror("DXF error", str(exc))
            return

        self._log(f"Found {len(layer_names)} layers: {', '.join(layer_names)}")

        # Parse layers and create instances
        parsed = parse_all_layers(layer_names)
        unit_scale = self._get_unit_scale()
        self._layer_instances = create_layer_instances(parsed, unit_scale)

        matched = [p for p in parsed if p.is_matched]
        unmatched = [p for p in parsed if not p.is_matched]

        self._log(f"✓ {len(matched)} layer(s) matched to element roles:", "SUCCESS")
        for pl in matched:
            dim_info = ""
            if pl.dimension_hint and pl.dimension_hint.dim1:
                dim_info = f"  (dims: {pl.dimension_hint.raw_match})"
            self._log(f"  {pl.layer_name} → {pl.role}{dim_info}")

        if unmatched:
            self._log(f"  {len(unmatched)} unmatched layer(s):", "WARN")
            for pl in unmatched:
                self._log(f"    {pl.layer_name}")

        # Populate tables
        self.structure_tab.populate_from_instances(self._layer_instances)
        self.loads_tab.populate_from_instances(self._layer_instances)

        self._log("Tables populated — switch to Structure/Loads tabs to review.")
        self._nb.select(1)  # switch to structure tab

    def _on_preview(self):
        """Run a DXF preview without launching RAM Concept."""
        if not self._layer_instances:
            messagebox.showinfo(
                "Process DXF First", "Click 'Process DXF' first to scan layers."
            )
            return

        dxf_path = self.v_dxf.get().strip()
        if not dxf_path:
            return

        self._nb.select(4)
        self._log("--- Preview: DXF geometry extraction ---", "INFO")

        # Sync table edits back
        self.structure_tab.collect_to_instances(self._layer_instances)
        self.loads_tab.collect_to_instances(self._layer_instances)

        # Build active layers map
        active = {}
        for li in self._layer_instances:
            if li.enabled:
                active[li.layer_name] = li.role

        unit_scale = self._get_unit_scale()
        try:
            result = import_dxf(dxf_path, active, unit_scale)
            self._import_result = result
        except Exception as exc:
            self._log(f"DXF read error: {exc}", "ERROR")
            return

        lines = [
            f"  Slab polygons:     {len(result.slab_polygons)}",
            f"  Beam segments:     {len(result.beam_segments)}",
            f"  Columns:           {len(result.column_geoms)}",
            f"  Wall segments:     {len(result.wall_segments)}",
            f"  Openings:          {len(result.opening_polygons)}",
            f"  Drop caps:         {len(result.drop_cap_polygons)}",
            f"  Drop panels:       {len(result.drop_panel_polygons)}",
            f"  Point supports:    {len(result.point_support_points)}",
            f"  Line supports:     {len(result.line_support_segments)}",
            f"  Area springs:      {len(result.area_spring_polygons)}",
            f"  ── Loads ──",
            f"  Line loads:        {len(result.line_load_segments)}",
            f"  Area loads:        {len(result.area_load_polygons)}",
            f"  Point loads:       {len(result.point_load_points)}",
        ]
        for l in lines:
            self._log(l)

        # Column shape info
        circulars = [cg for cg in result.column_geoms if cg.shape.is_circular]
        rects = [cg for cg in result.column_geoms if not cg.shape.is_circular]
        if circulars or rects:
            self._log(
                f"  Column shapes: {len(circulars)} circular, "
                f"{len(rects)} rectangular"
            )

        if result.skipped:
            self._log(f"  ⚠ Skipped: {len(result.skipped)}", "WARN")
            for s in result.skipped:
                self._log(f"    [{s.etype}] {s.layer}: {s.reason}", "WARN")

        total = (
            len(result.slab_polygons)
            + len(result.beam_segments)
            + len(result.column_geoms)
            + len(result.wall_segments)
        )
        if total == 0:
            self._log("⚠  No structural geometry found – check layer names.", "WARN")
        else:
            self._log("✓ Preview complete – ready to generate.", "SUCCESS")

    def _on_run(self):
        """Full pipeline: DXF → RAM Concept."""
        if not self._layer_instances:
            messagebox.showinfo(
                "Process DXF First", "Click 'Process DXF' first to scan layers."
            )
            return

        if not messagebox.askyesno(
            "Confirm Import",
            "This will start RAM Concept, consume a license seat, and "
            f"create/overwrite '{self.v_output.get()}'.\n\nContinue?",
        ):
            return

        self._nb.select(4)
        self._save_config()

        # Disable buttons
        for w in self.winfo_children():
            for child in w.winfo_children():
                try:
                    child.configure(state="disabled")
                except Exception:
                    pass

        thread = threading.Thread(target=self._run_worker, daemon=True)
        thread.start()

    def _run_worker(self):
        try:
            self._run_pipeline()
        except Exception:
            self._log("FATAL ERROR:\n" + traceback.format_exc(), "ERROR")
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Import Failed", "See Log tab for details."
                ),
            )
        finally:
            for w in self.winfo_children():
                for child in w.winfo_children():
                    try:
                        child.configure(state="normal")
                    except Exception:
                        pass

    def _run_pipeline(self):
        # 0. Sync tables
        self.structure_tab.collect_to_instances(self._layer_instances)
        self.loads_tab.collect_to_instances(self._layer_instances)

        # 1. Setup RAM Concept API
        api_path = self.v_api_path.get().strip()
        if api_path and api_path not in sys.path:
            sys.path.insert(1, api_path)

        try:
            from ram_concept.concept import Concept
            from ram_concept.model import DesignCode, StructureType
        except ImportError as exc:
            raise RuntimeError(
                "Cannot import 'ram_concept'. Set the API folder to the "
                "'python' subfolder inside your RAM Concept install."
            ) from exc

        # 2. Parse DXF
        dxf_path = self.v_dxf.get().strip()
        unit_scale = self._get_unit_scale()
        active = {li.layer_name: li.role for li in self._layer_instances if li.enabled}

        self._log(f"--- Parsing DXF: {Path(dxf_path).name} ---", "INFO")
        result = import_dxf(dxf_path, active, unit_scale)
        self._import_result = result

        total_geom = (
            len(result.slab_polygons)
            + len(result.beam_segments)
            + len(result.column_geoms)
            + len(result.wall_segments)
        )
        total_loads = (
            len(result.line_load_segments)
            + len(result.area_load_polygons)
            + len(result.point_load_points)
        )
        self._log(f"  Geometry: {total_geom} items  |  Loads: {total_loads} items")

        # 3. Build config
        config = ProjectConfig(
            dxf_path=dxf_path,
            output_cpt_path=self.v_output.get(),
            ram_api_path=api_path,
            design_code=self.v_design_code.get(),
            structure_type=self.v_struct_type.get(),
            unit_key=self.v_unit_key.get(),
            concrete=self.materials_tab.get_concrete_spec(),
            pt_system=self.materials_tab.get_pt_spec(),
            layer_instances=self._layer_instances,
            mesh_after=self.v_mesh_after.get(),
            headless=self.v_headless.get(),
        )

        # 4. Start RAM Concept
        self._log("Starting RAM Concept…", "INFO")
        concept = Concept.start_concept(headless=config.headless)
        try:
            model = concept.new_model()

            # Design code & structure type
            dc_str = DESIGN_CODES[config.design_code]
            st_str = STRUCTURE_TYPES[config.structure_type]
            dc_enum = getattr(DesignCode, dc_str)
            st_enum = getattr(StructureType, st_str)
            model.setup_new_model(dc_enum, st_enum)
            self._log(f"  Design code: {config.design_code}")
            self._log(f"  Structure type: {config.structure_type}")

            # 5. Add concrete
            from core.ram_builder import add_concrete_mix, build_structure
            from core.ram_loader import apply_loads

            self._log(f"  Adding concrete: {config.concrete.name}", "INFO")
            add_concrete_mix(model, config.concrete)

            # 6. Build structure
            self._log("--- Building structure ---", "INFO")
            build_summary = build_structure(
                model,
                result,
                config,
                log=lambda m: self._log(m),
                mesh_after=config.mesh_after,
            )

            # 7. Apply loads
            if total_loads > 0:
                self._log("--- Applying loads ---", "INFO")
                load_summary = apply_loads(
                    model,
                    result,
                    config,
                    log=lambda m: self._log(m),
                )
            else:
                self._log("  No load geometry found — skipping loads.")

            # 8. Save
            out = config.output_cpt_path.strip()
            self._log(f"Saving to: {out}", "INFO")
            model.save_file(out)
            self._log(f"✓ Saved successfully: {out}", "SUCCESS")

            # Summary
            self._log(
                f"\n✓ Import complete: "
                f"{build_summary.slabs_created} slabs | "
                f"{build_summary.walls_created} walls | "
                f"{build_summary.columns_created} columns | "
                f"{build_summary.beams_created} beams | "
                f"{build_summary.openings_created} openings | "
                f"{build_summary.drop_caps_created} drop-caps | "
                f"{build_summary.drop_panels_created} drop-panels",
                "SUCCESS",
            )
            if build_summary.errors:
                self._log(f"  ⚠ {len(build_summary.errors)} build error(s)", "WARN")

        finally:
            self._log("Shutting down RAM Concept…", "INFO")
            concept.shut_down()
            self._log("Done.", "INFO")
