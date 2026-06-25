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

from core.constants import UNIT_SCALES, DESIGN_CODES, STRUCTURE_TYPES, load_api_enums
from core.models import (
    ProjectConfig,
    LayerInstance,
    ConcreteSpec,
    PTSystemSpec,
)
from core.layer_parser import parse_all_layers, create_layer_instances
from core.dxf_reader import import_dxf, list_layers, ImportResult

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


def _safe_enum_lookup(enum_class, name: str, label: str):
    """Look up an enum member by name, with a helpful error on mismatch.
    
    Lists all valid members so the user can fix core/constants.py.
    """
    try:
        return getattr(enum_class, name)
    except AttributeError:
        members = [m for m in dir(enum_class)
                   if not m.startswith("_") and m[0].isupper()]
        raise AttributeError(
            f"{label} has no member '{name}'.\n"
            f"Valid members: {', '.join(sorted(members))}\n"
            f"Fix the mapping in core/constants.py to use one of these."
        )


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

        # ── Discover API enums ────────────────────────────────────────────────
        self._try_discover_api_enums()

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
        self.v_conc_name = tk.StringVar(value="C45")
        self.v_fc_final = tk.StringVar(value="45")
        self.v_fc_initial = tk.StringVar(value="30")

        # Auto-derive concrete name from fc_final
        self.v_fc_final.trace_add("write", self._on_fc_final_changed)
        self.v_poisson = tk.StringVar(value="0.2")
        self.v_unit_mass = tk.StringVar(value="2450")
        self.v_unit_mass_loads = tk.StringVar(value="2500")
        self.v_use_code_ec = tk.BooleanVar(value=True)
        # PT System
        self.v_use_pt_system = tk.BooleanVar(value=False)
        self.v_use_pt_strand = tk.BooleanVar(value=True)
        self.v_use_pt_duct = tk.BooleanVar(value=True)
        self.v_use_pt_anchor = tk.BooleanVar(value=True)
        self.v_pt_name = tk.StringVar(value="13mm Bonded")
        self.v_pt_strand = tk.StringVar(value="13mm Strand")
        self.v_pt_duct = tk.StringVar(value="4s Flat")
        self.v_pt_anchor = tk.StringVar(value="FA Multi")
        self.v_pt_aps = tk.StringVar(value="100")
        self.v_pt_eps = tk.StringVar(value="195000")
        self.v_pt_fse = tk.StringVar(value="1100")
        self.v_pt_fpy = tk.StringVar(value="1564")
        self.v_pt_fpu = tk.StringVar(value="1840")
        self.v_pt_duct_w = tk.StringVar(value="70")
        self.v_pt_duct_h = tk.StringVar(value="35")
        self.v_pt_strands = tk.StringVar(value="4")
        self.v_pt_sys_type = tk.StringVar(value="BONDED")
        self.v_pt_duct_shape = tk.StringVar(value="FLAT")
        self.v_pt_duct_type = tk.StringVar(value="CORRUGATED_STEEL")
        self.v_pt_anchor_type = tk.StringVar(value="FLAT_MULTI_PLANE")
        self.v_pt_min_radius = tk.StringVar(value="2.0")
        self.v_pt_anchor_friction = tk.StringVar(value="0.02")
        self.v_pt_angular_friction = tk.StringVar(value="0.2")
        self.v_pt_jack_stress = tk.StringVar(value="1564")
        self.v_pt_seating_distance = tk.StringVar(value="6")
        self.v_pt_long_losses = tk.StringVar(value="150")
        self.v_pt_wobble_friction = tk.StringVar(value="0.005")
        self.v_status = tk.StringVar(value="Select a DXF file, then process layers.")

    # ══════════════════════════════════════════════════════════════════════════
    # Layout
    # ══════════════════════════════════════════════════════════════════════════

    def _build_header(self):
        hdr = tk.Frame(self, bg=C_BG, height=78)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        title = tk.Frame(hdr, bg=C_BG)
        title.pack(side="left", padx=16, pady=(10, 8))
        tk.Label(
            title,
            text="DXF to RAM Concept",
            bg=C_BG,
            fg=C_TEXT,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title,
            text="Scan DXF layers, review properties, then generate the RAM Concept model.",
            bg=C_BG,
            fg="#CBD5E1",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(3, 0))

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
        ftr = tk.Frame(self, bg=C_BG, height=58)
        ftr.pack(fill="x")
        ftr.pack_propagate(False)

        status = tk.Frame(ftr, bg=C_BG)
        status.pack(side="left", fill="x", expand=True, padx=16)
        tk.Label(
            status,
            textvariable=self.v_status,
            bg=C_BG,
            fg=C_MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x", pady=18)

        actions = tk.Frame(ftr, bg=C_BG)
        actions.pack(side="right", padx=16, pady=10)
        styled_btn(actions, "Process DXF", self._on_process_dxf, accent=True).pack(
            side="left", padx=4
        )
        styled_btn(actions, "Preview", self._on_preview).pack(side="left", padx=4)
        styled_btn(actions, "Generate", self._on_run, accent=True).pack(side="left", padx=4)

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
            "use_pt_system": self.v_use_pt_system,
            "use_pt_strand": self.v_use_pt_strand,
            "use_pt_duct": self.v_use_pt_duct,
            "use_pt_anchor": self.v_use_pt_anchor,
            "pt_name": self.v_pt_name,
            "pt_strand": self.v_pt_strand,
            "pt_duct": self.v_pt_duct,
            "pt_anchor": self.v_pt_anchor,
            "pt_aps": self.v_pt_aps,
            "pt_eps": self.v_pt_eps,
            "pt_fse": self.v_pt_fse,
            "pt_fpy": self.v_pt_fpy,
            "pt_fpu": self.v_pt_fpu,
            "pt_duct_w": self.v_pt_duct_w,
            "pt_duct_h": self.v_pt_duct_h,
            "pt_strands": self.v_pt_strands,
            "pt_sys_type": self.v_pt_sys_type,
            "pt_duct_shape": self.v_pt_duct_shape,
            "pt_duct_type": self.v_pt_duct_type,
            "pt_anchor_type": self.v_pt_anchor_type,
            "pt_min_radius": self.v_pt_min_radius,
            "pt_anchor_friction": self.v_pt_anchor_friction,
            "pt_angular_friction": self.v_pt_angular_friction,
            "pt_jack_stress": self.v_pt_jack_stress,
            "pt_seating_distance": self.v_pt_seating_distance,
            "pt_long_losses": self.v_pt_long_losses,
            "pt_wobble_friction": self.v_pt_wobble_friction,
        }

    def _on_fc_final_changed(self, *args):
        """Auto-derive concrete name (e.g. 'C45') when fc_final changes."""
        val = self.v_fc_final.get().strip()
        try:
            fc = float(val)
            # Use integer formatting if it's a whole number
            if fc.is_integer():
                self.v_conc_name.set(f"C{int(fc)}")
            else:
                self.v_conc_name.set(f"C{fc}")
        except ValueError:
            pass  # if user is typing or typed invalid number, do nothing

    # ══════════════════════════════════════════════════════════════════════════
    # API Enum Discovery
    # ══════════════════════════════════════════════════════════════════════════

    def _try_discover_api_enums(self):
        """Discover design code / structure type enums from the API.
        
        Called at startup and whenever the API path changes.
        Updates the dropdown values in the Files tab.
        """
        api_path = self.v_api_path.get().strip()
        try:
            found = load_api_enums(api_path)
            if found:
                self._refresh_enum_dropdowns()
        except Exception:
            pass  # API not available — fallback values stay

    def _refresh_enum_dropdowns(self):
        """Refresh design code and structure type dropdowns with discovered values."""
        if hasattr(self, 'files_tab') and self.files_tab:
            self.files_tab.refresh_dropdowns()

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

        # Refresh enums from the real API now that it's imported
        load_api_enums(api_path)

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

            dc_enum = _safe_enum_lookup(DesignCode, dc_str, "DesignCode")
            st_enum = _safe_enum_lookup(StructureType, st_str, "StructureType")

            model.setup_new_model(dc_enum, st_enum)
            self._log(f"  Design code: {config.design_code} → {dc_str}")
            self._log(f"  Structure type: {config.structure_type} → {st_str}")

            # 5. Add concrete and optional PT definitions
            from core.ram_builder import (
                add_concrete_mix,
                add_pt_system_definition,
                build_structure,
            )
            from core.ram_loader import apply_loads

            self._log(f"  Adding concrete: {config.concrete.name}", "INFO")
            add_concrete_mix(model, config.concrete)

            if config.pt_system.use_pt_system:
                self._log(f"  Adding PT system: {config.pt_system.pt_name}", "INFO")
                add_pt_system_definition(
                    model,
                    config.pt_system,
                    log=lambda m: self._log(m),
                )
            else:
                self._log("  PT system disabled - skipping PT definitions.", "INFO")

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
