"""
dxf_to_concept_gui.py
=====================
Comprehensive Tkinter GUI for the DXF → RAM Concept structural importer.

Tabs
----
  1. Files & Units    – DXF path, output .cpt path, API path, unit scale,
                        design code, structure type
  2. Layer Mapping    – one row per element type: DXF layer name, enabled
                        toggle, quick-access to Properties dialog
  3. Element Properties – inline frames (Notebook within Notebook) for each
                          element type's spec parameters
  4. Log              – scrollable run log with colour-coded severity

Actions (toolbar)
-----------------
  • Scan Layers   – reads DXF layer names, colour-codes each mapping row
  • Preview       – runs dxf_importer only (no RAM Concept needed)
  • Run Import    – full pipeline: parse → open RAM Concept → build → save
  • Save Config   – persist current settings to config.json

All numbers are stored in their "display unit" (the unit the user chose) and
converted to metres for the builder only at run-time.
"""

from __future__ import annotations

import copy
import json
import queue
import sys
import threading
import traceback
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# -- project modules (same directory) -----------------------------------------
from layer_config import (
    DEFAULT_LAYER_MAP, DESIGN_CODES, STRUCTURE_TYPES, UNIT_SCALES,
    SlabSpec, WallSpec, ColumnSpec, BeamSpec,
    OpeningSpec, DropCapSpec, DropPanelSpec,
    PointSupportSpec, LineSupportSpec, AreaSpringSpec,
)
from dxf_importer  import import_dxf, list_layers
from ram_concept_builder import (
    build_structure, add_concrete_mix, BuildSummary,
)

CONFIG_PATH = Path(__file__).with_name("config.json")

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG        = "#1C2333"
C_PANEL     = "#232D42"
C_ACCENT    = "#3B82F6"
C_ACCENT2   = "#22D3EE"
C_TEXT      = "#E2E8F0"
C_MUTED     = "#94A3B8"
C_SUCCESS   = "#4ADE80"
C_WARN      = "#FACC15"
C_ERROR     = "#F87171"
C_ENTRY_BG  = "#2D3A52"
C_BORDER    = "#3B4A6A"

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULTS: dict = {
    "dxf_path":            "",
    "output_cpt_path":     str(Path.home() / "model_import.cpt"),
    "ram_api_path":        "",
    "unit_key":            "Millimetres (mm)",
    "unit_scale_custom":   "1.0",
    "design_code":         "ACI 318-14 (SI)",
    "structure_type":      "Elevated slab",
    "fc_mpa":              "40",
    "concrete_name":       "",     # blank → auto from fc_mpa
    # element enables
    "slab_enabled":        True,
    "wall_enabled":        True,
    "column_enabled":      True,
    "beam_enabled":        True,
    "opening_enabled":     True,
    "drop_cap_enabled":    True,
    "drop_panel_enabled":  True,
    "point_support_enabled": False,
    "line_support_enabled":  False,
    "area_spring_enabled":   False,
    # layer names (sync with DEFAULT_LAYER_MAP)
    "layer_slab":          "slab",
    "layer_wall":          "wall",
    "layer_column":        "column",
    "layer_beam":          "beam",
    "layer_opening":       "opening",
    "layer_drop_cap":      "drop_cap",
    "layer_drop_panel":    "drop_panel",
    "layer_point_support": "point_support",
    "layer_line_support":  "line_support",
    "layer_area_spring":   "area_spring",
    # slab
    "slab_thickness": "250", "slab_toc": "0", "slab_priority": "1",
    "slab_cover_top": "25",  "slab_cover_bot": "25",
    # wall
    "wall_thickness": "200", "wall_height": "3000",
    "wall_below_slab": True, "wall_shear": True,
    "wall_fixed_near": False, "wall_fixed_far": False,
    # column
    "col_b": "400", "col_d": "400", "col_height": "3000",
    "col_angle": "0", "col_below": True,
    "col_fixed_near": True, "col_fixed_far": True,
    # beam
    "beam_width": "300", "beam_depth": "500",
    "beam_no_torsion": False, "beam_priority": "2",
    # drop cap
    "dc_thickness": "400", "dc_priority": "3",
    # drop panel
    "dp_thickness": "350", "dp_priority": "2",
    # area spring
    "spring_kv": "40000", "spring_zero_tension": True,
    # misc
    "mesh_after": True,
    "headless": True,
}


# ── Config I/O ────────────────────────────────────────────────────────────────
def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text())
            cfg.update(saved)
        except Exception:
            pass
    return cfg


def save_config(cfg: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except Exception:
        pass


# ── Styled widget helpers ─────────────────────────────────────────────────────
def styled_entry(parent, textvariable, width=18, **kw):
    e = tk.Entry(parent, textvariable=textvariable, width=width,
                 bg=C_ENTRY_BG, fg=C_TEXT, insertbackground=C_TEXT,
                 relief="flat", bd=4, **kw)
    return e


def styled_check(parent, text, variable, **kw):
    return tk.Checkbutton(parent, text=text, variable=variable,
                          bg=C_PANEL, fg=C_TEXT, selectcolor=C_ENTRY_BG,
                          activebackground=C_PANEL, activeforeground=C_TEXT,
                          **kw)


def styled_label(parent, text, fg=C_TEXT, **kw):
    return tk.Label(parent, text=text, bg=C_PANEL, fg=fg, **kw)


def styled_btn(parent, text, command, accent=False, **kw):
    bg = C_ACCENT if accent else C_BORDER
    return tk.Button(parent, text=text, command=command,
                     bg=bg, fg=C_TEXT, activebackground=C_ACCENT2,
                     activeforeground="#0F172A", relief="flat",
                     bd=0, padx=10, pady=5, cursor="hand2", **kw)


def section_label(parent, text):
    f = tk.Frame(parent, bg=C_PANEL)
    tk.Label(f, text=text, bg=C_PANEL, fg=C_ACCENT2,
             font=("Segoe UI", 9, "bold")).pack(side="left")
    tk.Frame(f, bg=C_BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0))
    return f


# ── Unit conversion ──────────────────────────────────────────────────────────
def display_to_metres(value_str: str, unit_key: str, custom_scale: str) -> float:
    """Convert a numeric string in display units to metres."""
    v = float(value_str)
    if unit_key == "Custom…":
        scale = float(custom_scale)
    else:
        scale = UNIT_SCALES[unit_key]
    return v * scale


def m_label(unit_key: str) -> str:
    """Return a short unit abbreviation for display in property fields."""
    abbr = {
        "Millimetres (mm)": "mm",
        "Centimetres (cm)": "cm",
        "Metres (m)":       "m",
        "Inches (in)":      "in",
        "Feet (ft)":        "ft",
        "Custom…":          "?",
    }
    return abbr.get(unit_key, "m")


# ── Main Application ──────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DXF → RAM Concept Structural Importer  v2.0")
        self.geometry("950x820")
        self.minsize(820, 700)
        self.configure(bg=C_BG)
        self.cfg = load_config()
        self.log_queue: "queue.Queue[tuple[str,str]]" = queue.Queue()
        self._layer_map = copy.deepcopy(DEFAULT_LAYER_MAP)
        self._build_vars()
        self._build_ui()
        self.after(100, self._drain_log)

    # ── Variable setup ────────────────────────────────────────────────────────
    def _build_vars(self):
        cfg = self.cfg
        self.v_dxf          = tk.StringVar(value=cfg["dxf_path"])
        self.v_output       = tk.StringVar(value=cfg["output_cpt_path"])
        self.v_api_path     = tk.StringVar(value=cfg["ram_api_path"])
        self.v_unit_key     = tk.StringVar(value=cfg["unit_key"])
        self.v_unit_custom  = tk.StringVar(value=cfg["unit_scale_custom"])
        self.v_design_code  = tk.StringVar(value=cfg["design_code"])
        self.v_struct_type  = tk.StringVar(value=cfg["structure_type"])
        self.v_fc           = tk.StringVar(value=cfg["fc_mpa"])
        self.v_conc_name    = tk.StringVar(value=cfg["concrete_name"])
        self.v_mesh_after   = tk.BooleanVar(value=cfg["mesh_after"])
        self.v_headless     = tk.BooleanVar(value=cfg["headless"])

        # Auto-sync concrete name from f'c: "C{value}"
        self._sync_conc_name()                       # set initial value
        self.v_fc.trace_add("write", lambda *_: self._sync_conc_name())

        # Layer names & enables
        roles = ["slab","wall","column","beam","opening","drop_cap",
                 "drop_panel","point_support","line_support","area_spring"]
        self.v_layer   = {r: tk.StringVar(value=cfg[f"layer_{r}"])    for r in roles}
        self.v_enabled = {r: tk.BooleanVar(value=cfg[f"{r}_enabled"]) for r in roles}

        # Element property fields
        self.v_slab_t   = tk.StringVar(value=cfg["slab_thickness"])
        self.v_slab_toc = tk.StringVar(value=cfg["slab_toc"])
        self.v_slab_pri = tk.StringVar(value=cfg["slab_priority"])
        self.v_slab_cov_t = tk.StringVar(value=cfg["slab_cover_top"])
        self.v_slab_cov_b = tk.StringVar(value=cfg["slab_cover_bot"])

        self.v_wall_t   = tk.StringVar(value=cfg["wall_thickness"])
        self.v_wall_h   = tk.StringVar(value=cfg["wall_height"])
        self.v_wall_bs  = tk.BooleanVar(value=cfg["wall_below_slab"])
        self.v_wall_sw  = tk.BooleanVar(value=cfg["wall_shear"])
        self.v_wall_fn  = tk.BooleanVar(value=cfg["wall_fixed_near"])
        self.v_wall_ff  = tk.BooleanVar(value=cfg["wall_fixed_far"])

        self.v_col_b    = tk.StringVar(value=cfg["col_b"])
        self.v_col_d    = tk.StringVar(value=cfg["col_d"])
        self.v_col_h    = tk.StringVar(value=cfg["col_height"])
        self.v_col_ang  = tk.StringVar(value=cfg["col_angle"])
        self.v_col_bs   = tk.BooleanVar(value=cfg["col_below"])
        self.v_col_fn   = tk.BooleanVar(value=cfg["col_fixed_near"])
        self.v_col_ff   = tk.BooleanVar(value=cfg["col_fixed_far"])

        self.v_beam_w   = tk.StringVar(value=cfg["beam_width"])
        self.v_beam_d   = tk.StringVar(value=cfg["beam_depth"])
        self.v_beam_nt  = tk.BooleanVar(value=cfg["beam_no_torsion"])
        self.v_beam_pri = tk.StringVar(value=cfg["beam_priority"])

        self.v_dc_t     = tk.StringVar(value=cfg["dc_thickness"])
        self.v_dc_pri   = tk.StringVar(value=cfg["dc_priority"])
        self.v_dp_t     = tk.StringVar(value=cfg["dp_thickness"])
        self.v_dp_pri   = tk.StringVar(value=cfg["dp_priority"])

        self.v_spring_kv  = tk.StringVar(value=cfg["spring_kv"])
        self.v_spring_zt  = tk.BooleanVar(value=cfg["spring_zero_tension"])

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = tk.Frame(self, bg=C_PANEL, pady=6)
        tb.pack(fill="x", side="top")
        tk.Label(tb, text="DXF  →  RAM Concept", bg=C_PANEL,
                 fg=C_ACCENT2, font=("Segoe UI", 12, "bold")).pack(side="left", padx=12)

        for txt, cmd, acc in [
            ("Scan Layers",  self._scan_layers,  False),
            ("Preview DXF",  self._on_preview,   False),
            ("▶  Run Import", self._on_run,       True),
            ("Save Config",  self._save_cfg,      False),
        ]:
            styled_btn(tb, txt, cmd, accent=acc).pack(side="left", padx=4)

        # ── Notebook ─────────────────────────────────────────────────────────
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Dark.TNotebook",       background=C_BG, borderwidth=0)
        style.configure("Dark.TNotebook.Tab",   background=C_PANEL, foreground=C_MUTED,
                        padding=[12, 5], font=("Segoe UI", 9))
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", C_ACCENT)],
                  foreground=[("selected", "#FFFFFF")])

        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        tab1 = tk.Frame(nb, bg=C_PANEL)
        tab2 = tk.Frame(nb, bg=C_PANEL)
        tab3 = tk.Frame(nb, bg=C_PANEL)
        tab4 = tk.Frame(nb, bg=C_PANEL)
        nb.add(tab1, text="  Files & Units  ")
        nb.add(tab2, text="  Layer Mapping  ")
        nb.add(tab3, text="  Element Properties  ")
        nb.add(tab4, text="  Run Log  ")

        self._build_tab_files(tab1)
        self._build_tab_layers(tab2)
        self._build_tab_props(tab3)
        self._build_tab_log(tab4)

        self._nb = nb

    # ── Tab 1: Files & Units ─────────────────────────────────────────────────
    def _build_tab_files(self, parent):
        def row(f, label, var, browse_cmd=None, width=42):
            tk.Label(f, text=label, bg=C_PANEL, fg=C_MUTED,
                     width=30, anchor="w").grid(row=f._r, column=0, sticky="w", padx=8, pady=3)
            e = styled_entry(f, var, width=width)
            e.grid(row=f._r, column=1, sticky="we", padx=4)
            if browse_cmd:
                styled_btn(f, "…", browse_cmd).grid(row=f._r, column=2, padx=4)
            f._r += 1
            return e

        # ── File paths ────────────────────────────────────────────────────────
        f = tk.Frame(parent, bg=C_PANEL)
        f.pack(fill="x", padx=16, pady=10)
        f._r = 0
        section_label(parent, "  File Paths").pack(fill="x", padx=16, pady=(12,0))
        f.columnconfigure(1, weight=1)

        row(f, "DXF input file:", self.v_dxf, self._browse_dxf)
        row(f, "Output .cpt file:", self.v_output, self._browse_cpt)
        row(f, "RAM Concept API folder:", self.v_api_path, self._browse_api)

        # ── Units ─────────────────────────────────────────────────────────────
        section_label(parent, "  Units & Scale").pack(fill="x", padx=16, pady=(12,0))
        uf = tk.Frame(parent, bg=C_PANEL)
        uf.pack(fill="x", padx=16, pady=6)
        tk.Label(uf, text="DXF drawing units:", bg=C_PANEL, fg=C_MUTED).grid(row=0, column=0, sticky="w", padx=8)
        unit_dd = ttk.Combobox(uf, textvariable=self.v_unit_key,
                               values=list(UNIT_SCALES.keys()), width=24, state="readonly")
        unit_dd.grid(row=0, column=1, padx=4, sticky="w")
        unit_dd.bind("<<ComboboxSelected>>", lambda e: self._on_unit_change())
        self._custom_scale_lbl = tk.Label(uf, text="Custom scale:", bg=C_PANEL, fg=C_MUTED)
        self._custom_scale_ent = styled_entry(uf, self.v_unit_custom, width=10)
        self._on_unit_change()   # show/hide custom row

        # ── Design settings ───────────────────────────────────────────────────
        section_label(parent, "  Design Code & Structure Type").pack(fill="x", padx=16, pady=(12,0))
        df = tk.Frame(parent, bg=C_PANEL)
        df.pack(fill="x", padx=16, pady=6)
        tk.Label(df, text="Design code:", bg=C_PANEL, fg=C_MUTED).grid(row=0, column=0, sticky="w", padx=8)
        ttk.Combobox(df, textvariable=self.v_design_code,
                     values=list(DESIGN_CODES.keys()), width=26, state="readonly"
                     ).grid(row=0, column=1, padx=4, sticky="w")
        tk.Label(df, text="Structure type:", bg=C_PANEL, fg=C_MUTED).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(df, textvariable=self.v_struct_type,
                     values=list(STRUCTURE_TYPES.keys()), width=26, state="readonly"
                     ).grid(row=1, column=1, padx=4, sticky="w")

        # ── Concrete ──────────────────────────────────────────────────────────
        section_label(parent, "  Concrete Mix").pack(fill="x", padx=16, pady=(12,0))
        cf = tk.Frame(parent, bg=C_PANEL)
        cf.pack(fill="x", padx=16, pady=6)
        tk.Label(cf, text="f'c (MPa):", bg=C_PANEL, fg=C_MUTED).grid(row=0, column=0, sticky="w", padx=8)
        styled_entry(cf, self.v_fc, width=10).grid(row=0, column=1, sticky="w")
        tk.Label(cf, text="Concrete name:", bg=C_PANEL, fg=C_MUTED).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        tk.Entry(cf, textvariable=self.v_conc_name, width=22,
                 state="readonly", fg="#000000", readonlybackground=C_ENTRY_BG,
                 relief="flat", bd=4).grid(row=1, column=1, sticky="w")

        # ── Options ───────────────────────────────────────────────────────────
        section_label(parent, "  Options").pack(fill="x", padx=16, pady=(12,0))
        of = tk.Frame(parent, bg=C_PANEL)
        of.pack(fill="x", padx=16, pady=6)
        styled_check(of, "Generate mesh after import", self.v_mesh_after).pack(side="left", padx=8)
        styled_check(of, "Run RAM Concept headless (no GUI)", self.v_headless).pack(side="left", padx=8)

    def _sync_conc_name(self):
        """Keep concrete name in sync with f'c: e.g. f'c=40 → 'C40'."""
        raw = self.v_fc.get().strip()
        try:
            val = float(raw)
            # Use int form if it's a whole number (C40 not C40.0)
            name = f"C{int(val)}" if val == int(val) else f"C{val}"
        except (ValueError, OverflowError):
            name = ""
        self.v_conc_name.set(name)

    def _on_unit_change(self):
        key = self.v_unit_key.get()
        if key == "Custom…":
            self._custom_scale_lbl.grid(row=1, column=0, sticky="w", padx=8, pady=4)
            self._custom_scale_ent.grid(row=1, column=1, padx=4, sticky="w")
        else:
            try:
                self._custom_scale_lbl.grid_remove()
                self._custom_scale_ent.grid_remove()
            except Exception:
                pass

    # ── Tab 2: Layer Mapping ──────────────────────────────────────────────────
    def _build_tab_layers(self, parent):
        ROLES = [
            ("slab",          "Slab",           "Closed polygon outlines – one per slab region"),
            ("wall",          "Wall",            "LINE / POLYLINE centrelines"),
            ("column",        "Column",          "POINT / CIRCLE / INSERT (block ref)"),
            ("beam",          "Beam",            "LINE / POLYLINE beam centrelines"),
            ("opening",       "Slab Opening",    "Closed polygon outlines of voids"),
            ("drop_cap",      "Drop Cap",        "Closed polygon – high-priority thick slab"),
            ("drop_panel",    "Drop Panel",      "Closed polygon – medium-priority thick slab"),
            ("point_support", "Point Support",   "POINT / CIRCLE (for mat/raft)"),
            ("line_support",  "Line Support",    "LINE / POLYLINE (for mat/raft)"),
            ("area_spring",   "Area Spring",     "Closed polygon – soil spring region"),
        ]

        hdr = tk.Frame(parent, bg=C_BORDER)
        hdr.pack(fill="x", padx=12, pady=(12, 0))
        for txt, w in [("Enabled", 7), ("Element Type", 15), ("DXF Layer Name", 20), ("Notes", 40)]:
            tk.Label(hdr, text=txt, bg=C_BORDER, fg=C_ACCENT2,
                     width=w, font=("Segoe UI", 8, "bold")).pack(side="left", padx=4, pady=4)

        self._layer_rows: dict[str, tk.Frame] = {}
        canvas = tk.Canvas(parent, bg=C_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=12, pady=4)

        inner = tk.Frame(canvas, bg=C_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        for role, label, note in ROLES:
            fr = tk.Frame(inner, bg=C_PANEL, pady=2)
            fr.pack(fill="x")
            styled_check(fr, "", self.v_enabled[role]
                         ).pack(side="left", padx=4)
            tk.Label(fr, text=label, bg=C_PANEL, fg=C_TEXT,
                     width=16, anchor="w").pack(side="left")
            styled_entry(fr, self.v_layer[role], width=22
                         ).pack(side="left", padx=4)
            tk.Label(fr, text=note, bg=C_PANEL, fg=C_MUTED,
                     font=("Segoe UI", 8)).pack(side="left", padx=4)
            self._layer_rows[role] = fr

        # Legend
        leg = tk.Frame(parent, bg=C_PANEL)
        leg.pack(fill="x", padx=12, pady=6)
        for col, lbl in [(C_SUCCESS, "Layer found in DXF"), (C_ERROR, "Layer NOT in DXF"),
                         (C_TEXT, "Not scanned yet")]:
            f2 = tk.Frame(leg, bg=col, width=12, height=12)
            f2.pack(side="left", padx=(8, 2))
            tk.Label(leg, text=lbl, bg=C_PANEL, fg=C_MUTED,
                     font=("Segoe UI", 8)).pack(side="left", padx=(0, 12))

    # ── Tab 3: Element Properties ─────────────────────────────────────────────
    def _build_tab_props(self, parent):
        nb2 = ttk.Notebook(parent, style="Dark.TNotebook")
        nb2.pack(fill="both", expand=True, padx=8, pady=8)

        panes = {
            "Slab":         self._props_slab,
            "Wall":         self._props_wall,
            "Column":       self._props_column,
            "Beam":         self._props_beam,
            "Drop Cap":     self._props_drop_cap,
            "Drop Panel":   self._props_drop_panel,
            "Springs":      self._props_springs,
        }
        for name, builder in panes.items():
            f = tk.Frame(nb2, bg=C_PANEL)
            nb2.add(f, text=f"  {name}  ")
            builder(f)

    def _props_field(self, parent, row_idx, label, var, unit="", note=""):
        tk.Label(parent, text=label, bg=C_PANEL, fg=C_MUTED,
                 width=28, anchor="w").grid(row=row_idx, column=0, sticky="w", padx=10, pady=4)
        styled_entry(parent, var, width=14).grid(row=row_idx, column=1, sticky="w")
        if unit:
            tk.Label(parent, text=unit, bg=C_PANEL, fg=C_MUTED,
                     font=("Segoe UI", 8)).grid(row=row_idx, column=2, sticky="w", padx=4)
        if note:
            tk.Label(parent, text=note, bg=C_PANEL, fg=C_MUTED,
                     font=("Segoe UI", 8, "italic")).grid(row=row_idx, column=3, sticky="w", padx=4)

    def _props_slab(self, p):
        r = 0
        section_label(p, "  Slab Area Defaults").grid(row=r, column=0, columnspan=4, sticky="we", padx=8, pady=(12,4)); r+=1
        unit = m_label(self.v_unit_key.get())
        for lbl, var, u, note in [
            ("Thickness:", self.v_slab_t, unit, "e.g. 250 mm"),
            ("Top of concrete (toc):", self.v_slab_toc, unit, "0 = ground level"),
            ("Priority:", self.v_slab_pri, "", "Higher = takes precedence at overlaps"),
            ("Cover top:", self.v_slab_cov_t, unit, "Clear cover, reinforcement"),
            ("Cover bottom:", self.v_slab_cov_b, unit, ""),
        ]:
            self._props_field(p, r, lbl, var, u, note); r += 1

    def _props_wall(self, p):
        r = 0
        section_label(p, "  Wall Defaults").grid(row=r, column=0, columnspan=4, sticky="we", padx=8, pady=(12,4)); r+=1
        unit = m_label(self.v_unit_key.get())
        for lbl, var, u, note in [
            ("Thickness:", self.v_wall_t, unit, ""),
            ("Storey height:", self.v_wall_h, unit, ""),
        ]:
            self._props_field(p, r, lbl, var, u, note); r += 1
        styled_check(p, "Below slab", self.v_wall_bs).grid(row=r, column=0, sticky="w", padx=10, pady=4); r+=1
        styled_check(p, "Shear wall", self.v_wall_sw).grid(row=r, column=0, sticky="w", padx=10, pady=4); r+=1
        styled_check(p, "Fixed near end", self.v_wall_fn).grid(row=r, column=0, sticky="w", padx=10, pady=4); r+=1
        styled_check(p, "Fixed far end",  self.v_wall_ff).grid(row=r, column=0, sticky="w", padx=10, pady=4)

    def _props_column(self, p):
        r = 0
        section_label(p, "  Column Defaults").grid(row=r, column=0, columnspan=4, sticky="we", padx=8, pady=(12,4)); r+=1
        unit = m_label(self.v_unit_key.get())
        for lbl, var, u, note in [
            ("Width b:", self.v_col_b, unit, ""),
            ("Depth d:", self.v_col_d, unit, ""),
            ("Storey height:", self.v_col_h, unit, ""),
            ("Angle (°):", self.v_col_ang, "°", "Rotation from X-axis"),
        ]:
            self._props_field(p, r, lbl, var, u, note); r += 1
        styled_check(p, "Below slab", self.v_col_bs).grid(row=r, column=0, sticky="w", padx=10, pady=4); r+=1
        styled_check(p, "Fixed near (base)", self.v_col_fn).grid(row=r, column=0, sticky="w", padx=10); r+=1
        styled_check(p, "Fixed far (top)", self.v_col_ff).grid(row=r, column=0, sticky="w", padx=10, pady=4)
        tk.Label(p, text="💡 Per-block size overrides: add block_size_map to ColumnSpec in layer_config.py",
                 bg=C_PANEL, fg=C_MUTED, font=("Segoe UI", 8, "italic"), wraplength=400, justify="left"
                 ).grid(row=r+1, column=0, columnspan=4, sticky="w", padx=10, pady=8)

    def _props_beam(self, p):
        r = 0
        section_label(p, "  Beam Defaults").grid(row=r, column=0, columnspan=4, sticky="we", padx=8, pady=(12,4)); r+=1
        unit = m_label(self.v_unit_key.get())
        for lbl, var, u, note in [
            ("Width:", self.v_beam_w, unit, ""),
            ("Overall depth:", self.v_beam_d, unit, "Including slab thickness for downstand"),
            ("Priority:", self.v_beam_pri, "", "2 beats slab(1), drop-cap(3) beats beam"),
        ]:
            self._props_field(p, r, lbl, var, u, note); r += 1
        styled_check(p, "No torsion (recommended for band beams)", self.v_beam_nt
                     ).grid(row=r, column=0, columnspan=4, sticky="w", padx=10, pady=4)

    def _props_drop_cap(self, p):
        r = 0
        section_label(p, "  Drop Cap Defaults (high-priority slab area)").grid(
            row=r, column=0, columnspan=4, sticky="we", padx=8, pady=(12,4)); r+=1
        unit = m_label(self.v_unit_key.get())
        self._props_field(p, r, "Total thickness:", self.v_dc_t, unit, "Slab + cap combined"); r+=1
        self._props_field(p, r, "Priority:", self.v_dc_pri, "", "Must exceed slab & drop-panel priority")

    def _props_drop_panel(self, p):
        r = 0
        section_label(p, "  Drop Panel Defaults (medium-priority slab area)").grid(
            row=r, column=0, columnspan=4, sticky="we", padx=8, pady=(12,4)); r+=1
        unit = m_label(self.v_unit_key.get())
        self._props_field(p, r, "Total thickness:", self.v_dp_t, unit, ""); r+=1
        self._props_field(p, r, "Priority:", self.v_dp_pri, "", "")

    def _props_springs(self, p):
        r = 0
        section_label(p, "  Area Spring Defaults (for Mat / Raft foundations)").grid(
            row=r, column=0, columnspan=4, sticky="we", padx=8, pady=(12,4)); r+=1
        self._props_field(p, r, "Vertical spring kv (kN/m³):", self.v_spring_kv, "kN/m³",
                          "40 000 = stiff clay, 100 000+ = rock"); r+=1
        styled_check(p, "Zero tension (soil can't pull slab)", self.v_spring_zt
                     ).grid(row=r, column=0, columnspan=4, sticky="w", padx=10, pady=4)
        tk.Label(p, text="Point supports and line supports have no configurable spring in basic mode.\n"
                         "Edit PointSupportSpec / LineSupportSpec in layer_config.py for spring stiffnesses.",
                 bg=C_PANEL, fg=C_MUTED, font=("Segoe UI", 8, "italic"), justify="left"
                 ).grid(row=r+1, column=0, columnspan=4, sticky="w", padx=10, pady=8)

    # ── Tab 4: Log ────────────────────────────────────────────────────────────
    def _build_tab_log(self, parent):
        ctrl = tk.Frame(parent, bg=C_PANEL)
        ctrl.pack(fill="x", padx=8, pady=4)
        styled_btn(ctrl, "Clear Log", self._clear_log).pack(side="left", padx=4)
        styled_btn(ctrl, "Copy All",  self._copy_log).pack(side="left", padx=4)

        self.log_text = tk.Text(parent, bg="#0F172A", fg=C_TEXT,
                                insertbackground=C_TEXT, font=("Consolas", 9),
                                wrap="word", state="disabled", relief="flat")
        sb = ttk.Scrollbar(parent, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=4)

        self.log_text.tag_configure("WARN",    foreground=C_WARN)
        self.log_text.tag_configure("ERROR",   foreground=C_ERROR)
        self.log_text.tag_configure("SUCCESS", foreground=C_SUCCESS)
        self.log_text.tag_configure("INFO",    foreground=C_ACCENT2)
        self.log_text.tag_configure("NORMAL",  foreground=C_TEXT)

    # ── Browsing helpers ──────────────────────────────────────────────────────
    def _browse_dxf(self):
        p = filedialog.askopenfilename(filetypes=[("DXF files", "*.dxf"), ("All", "*.*")])
        if p: self.v_dxf.set(p)

    def _browse_cpt(self):
        p = filedialog.asksaveasfilename(defaultextension=".cpt",
            filetypes=[("RAM Concept", "*.cpt"), ("All", "*.*")])
        if p: self.v_output.set(p)

    def _browse_api(self):
        p = filedialog.askdirectory(title="Select RAM Concept 'python' folder")
        if p: self.v_api_path.set(p)

    # ── Scan DXF layers ───────────────────────────────────────────────────────
    def _scan_layers(self):
        dxf = self.v_dxf.get().strip()
        if not dxf or not Path(dxf).exists():
            messagebox.showerror("No DXF", "Select a DXF file first.")
            return
        try:
            layers = set(list_layers(dxf))
        except Exception as exc:
            messagebox.showerror("Scan failed", str(exc))
            return
        for role, fr in self._layer_rows.items():
            lname = self.v_layer[role].get()
            # Subtle tints that blend with the dark theme
            row_bg = "#1B3329" if lname in layers else "#3B2020"   # dark green / dark red tint
            indicator_fg = C_SUCCESS if lname in layers else "#E57373"  # bright green / soft red for text
            fr.configure(bg=row_bg)
            for child in fr.winfo_children():
                try:
                    if isinstance(child, tk.Label):
                        child.configure(bg=row_bg)
                    elif isinstance(child, tk.Checkbutton):
                        child.configure(bg=row_bg, activebackground=row_bg)
                except Exception:
                    pass
        self._log(f"Layers in '{Path(dxf).name}': {', '.join(sorted(layers))}", "INFO")
        # Jump to layer tab
        self._nb.select(1)

    # ── Log helpers ───────────────────────────────────────────────────────────
    def _log(self, msg: str, level: str = "NORMAL"):
        self.log_queue.put((msg, level))

    def _drain_log(self):
        try:
            while True:
                msg, level = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                if "error" in msg.lower() or "failed" in msg.lower() or "fatal" in msg.lower():
                    tag = "ERROR"
                elif "⚠" in msg or "warn" in msg.lower() or "skip" in msg.lower():
                    tag = "WARN"
                elif "✓" in msg or "complete" in msg.lower() or "saved" in msg.lower() or "success" in msg.lower():
                    tag = "SUCCESS"
                elif "---" in msg or msg.startswith("Adding") or msg.startswith("Generat"):
                    tag = "INFO"
                else:
                    tag = level
                self.log_text.insert("end", msg + "\n", tag)
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_log)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _copy_log(self):
        content = self.log_text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(content)

    # ── Config helpers ────────────────────────────────────────────────────────
    def _current_config(self) -> dict:
        return {
            "dxf_path":            self.v_dxf.get(),
            "output_cpt_path":     self.v_output.get(),
            "ram_api_path":        self.v_api_path.get(),
            "unit_key":            self.v_unit_key.get(),
            "unit_scale_custom":   self.v_unit_custom.get(),
            "design_code":         self.v_design_code.get(),
            "structure_type":      self.v_struct_type.get(),
            "fc_mpa":              self.v_fc.get(),
            "concrete_name":       self.v_conc_name.get(),
            "mesh_after":          self.v_mesh_after.get(),
            "headless":            self.v_headless.get(),
            # layer names
            **{f"layer_{r}": self.v_layer[r].get() for r in self.v_layer},
            # enables
            **{f"{r}_enabled": self.v_enabled[r].get() for r in self.v_enabled},
            # props
            "slab_thickness": self.v_slab_t.get(), "slab_toc": self.v_slab_toc.get(),
            "slab_priority":  self.v_slab_pri.get(), "slab_cover_top": self.v_slab_cov_t.get(),
            "slab_cover_bot": self.v_slab_cov_b.get(),
            "wall_thickness": self.v_wall_t.get(), "wall_height": self.v_wall_h.get(),
            "wall_below_slab": self.v_wall_bs.get(), "wall_shear": self.v_wall_sw.get(),
            "wall_fixed_near": self.v_wall_fn.get(), "wall_fixed_far": self.v_wall_ff.get(),
            "col_b": self.v_col_b.get(), "col_d": self.v_col_d.get(),
            "col_height": self.v_col_h.get(), "col_angle": self.v_col_ang.get(),
            "col_below": self.v_col_bs.get(), "col_fixed_near": self.v_col_fn.get(),
            "col_fixed_far": self.v_col_ff.get(),
            "beam_width": self.v_beam_w.get(), "beam_depth": self.v_beam_d.get(),
            "beam_no_torsion": self.v_beam_nt.get(), "beam_priority": self.v_beam_pri.get(),
            "dc_thickness": self.v_dc_t.get(), "dc_priority": self.v_dc_pri.get(),
            "dp_thickness": self.v_dp_t.get(), "dp_priority": self.v_dp_pri.get(),
            "spring_kv": self.v_spring_kv.get(), "spring_zero_tension": self.v_spring_zt.get(),
        }

    def _save_cfg(self):
        save_config(self._current_config())
        self._log("✓ Configuration saved to config.json", "SUCCESS")

    # ── Build the live layer_map from GUI vars ────────────────────────────────
    def _build_layer_map(self, cfg: dict) -> dict:
        """Produce a layer_map dict ready for import_dxf / build_structure."""
        import copy
        lm = copy.deepcopy(DEFAULT_LAYER_MAP)
        unit_key    = cfg["unit_key"]
        unit_custom = cfg["unit_scale_custom"]

        def m(val_str: str) -> float:
            return display_to_metres(val_str, unit_key, unit_custom)

        # Update layer names and enables
        for role in lm:
            lm[role].layer   = cfg.get(f"layer_{role}", lm[role].layer)
            lm[role].enabled = cfg.get(f"{role}_enabled", lm[role].enabled)

        # Update spec values from GUI
        s: SlabSpec = lm["slab"].spec
        s.thickness  = m(cfg["slab_thickness"])
        s.toc        = m(cfg["slab_toc"])
        s.priority   = int(cfg["slab_priority"])

        w: WallSpec = lm["wall"].spec
        w.thickness  = m(cfg["wall_thickness"])
        w.height     = m(cfg["wall_height"])
        w.below_slab = bool(cfg["wall_below_slab"])
        w.shear_wall = bool(cfg["wall_shear"])
        w.fixed_near = bool(cfg["wall_fixed_near"])
        w.fixed_far  = bool(cfg["wall_fixed_far"])

        c: ColumnSpec = lm["column"].spec
        c.b          = m(cfg["col_b"])
        c.d          = m(cfg["col_d"])
        c.height     = m(cfg["col_height"])
        c.angle      = float(cfg["col_angle"])
        c.below_slab = bool(cfg["col_below"])
        c.fixed_near = bool(cfg["col_fixed_near"])
        c.fixed_far  = bool(cfg["col_fixed_far"])

        bm: BeamSpec = lm["beam"].spec
        bm.width     = m(cfg["beam_width"])
        bm.depth     = m(cfg["beam_depth"])
        bm.no_torsion = bool(cfg["beam_no_torsion"])
        bm.priority  = int(cfg["beam_priority"])

        dc: DropCapSpec = lm["drop_cap"].spec
        dc.thickness = m(cfg["dc_thickness"])
        dc.priority  = int(cfg["dc_priority"])

        dp: DropPanelSpec = lm["drop_panel"].spec
        dp.thickness = m(cfg["dp_thickness"])
        dp.priority  = int(cfg["dp_priority"])

        sp: AreaSpringSpec = lm["area_spring"].spec
        sp.kv           = float(cfg["spring_kv"])
        sp.zero_tension = bool(cfg["spring_zero_tension"])

        # Set concrete name on all specs
        fc   = float(cfg["fc_mpa"])
        name = cfg["concrete_name"].strip() or f"{int(fc)} MPa"
        for role in lm:
            spec = lm[role].spec
            if hasattr(spec, "concrete_name"):
                spec.concrete_name = name

        return lm

    # ── Validate inputs ───────────────────────────────────────────────────────
    def _validate(self) -> Optional[dict]:
        cfg = self._current_config()
        dxf = cfg["dxf_path"].strip()
        if not dxf or not Path(dxf).exists():
            messagebox.showerror("Missing file", "Select a valid DXF file on the Files & Units tab.")
            return None
        # Check all numeric fields
        numeric_fields = [
            "fc_mpa", "slab_thickness", "slab_toc", "slab_priority",
            "wall_thickness", "wall_height", "col_b", "col_d", "col_height",
            "col_angle", "beam_width", "beam_depth", "beam_priority",
            "dc_thickness", "dc_priority", "dp_thickness", "dp_priority",
            "spring_kv",
        ]
        for f in numeric_fields:
            try:
                float(cfg[f])
            except (ValueError, KeyError):
                messagebox.showerror("Invalid value", f"Field '{f}' must be a number. Got: {cfg.get(f)!r}")
                return None
        save_config(cfg)
        return cfg

    # ── Preview action ────────────────────────────────────────────────────────
    def _on_preview(self):
        cfg = self._validate()
        if not cfg: return
        lm = self._build_layer_map(cfg)
        scale = UNIT_SCALES.get(cfg["unit_key"], float(cfg["unit_scale_custom"]))
        self._nb.select(3)      # switch to log tab
        self._log(f"--- Preview: {Path(cfg['dxf_path']).name} ---", "INFO")
        try:
            result = import_dxf(cfg["dxf_path"], lm, unit_scale=scale)
        except Exception as exc:
            self._log(f"DXF read error: {exc}", "ERROR")
            messagebox.showerror("DXF error", str(exc)); return

        lines = [
            f"Wall segments:     {len(result.wall_segments)}",
            f"Beam segments:     {len(result.beam_segments)}",
            f"Columns:           {len(result.column_points)}",
            f"Slab polygons:     {len(result.slab_polygons)}",
            f"Openings:          {len(result.opening_polygons)}",
            f"Drop caps:         {len(result.drop_cap_polygons)}",
            f"Drop panels:       {len(result.drop_panel_polygons)}",
            f"Point supports:    {len(result.point_support_points)}",
            f"Line supports:     {len(result.line_support_segments)}",
            f"Area springs:      {len(result.area_spring_polygons)}",
        ]
        for l in lines: self._log("  " + l)
        if result.skipped:
            self._log(f"  Skipped DXF entities: {len(result.skipped)}", "WARN")
            for s in result.skipped:
                self._log(f"    [{s.etype}] layer='{s.layer}': {s.reason}", "WARN")
        if not any([result.wall_segments, result.column_points, result.slab_polygons,
                    result.beam_segments]):
            self._log("  ⚠  Nothing found – check layer names match your DXF exactly.", "WARN")
            self._log(f"  Layers in file: {', '.join(result.available_layers)}", "INFO")
        else:
            self._log("✓ Preview complete – looks good to import.", "SUCCESS")

    # ── Full import run ───────────────────────────────────────────────────────
    def _on_run(self):
        cfg = self._validate()
        if not cfg: return
        if not messagebox.askyesno(
            "Confirm Import",
            "This will start RAM Concept, consume a license seat, and create/overwrite "
            f"'{cfg['output_cpt_path']}'.\n\nContinue?",
        ):
            return
        self._nb.select(3)
        for w in self.winfo_children():
            if isinstance(w, tk.Frame):
                for b in w.winfo_children():
                    try: b.configure(state="disabled")
                    except Exception: pass
        thread = threading.Thread(target=self._run_worker, args=(cfg,), daemon=True)
        thread.start()

    def _run_worker(self, cfg: dict):
        try:
            self._run_pipeline(cfg)
        except Exception:
            self._log("FATAL ERROR:\n" + traceback.format_exc(), "ERROR")
            self.after(0, lambda: messagebox.showerror("Import failed", "See Run Log for details."))
        finally:
            # Re-enable buttons
            for w in self.winfo_children():
                if isinstance(w, tk.Frame):
                    for b in w.winfo_children():
                        try: b.configure(state="normal")
                        except Exception: pass

    def _run_pipeline(self, cfg: dict):
        # 1  Set up RAM Concept API path
        api_path = cfg["ram_api_path"].strip()
        if api_path and api_path not in sys.path:
            sys.path.insert(1, api_path)

        try:
            from ram_concept.concept import Concept
            from ram_concept.model   import DesignCode, StructureType
        except ImportError as exc:
            raise RuntimeError(
                "Cannot import 'ram_concept'. Point the 'RAM Concept API folder' field at "
                "the 'python' subfolder inside your RAM Concept install directory."
            ) from exc

        # 2  Parse DXF
        scale = UNIT_SCALES.get(cfg["unit_key"], float(cfg["unit_scale_custom"]))
        lm    = self._build_layer_map(cfg)
        self._log(f"--- Parsing DXF: {Path(cfg['dxf_path']).name} ---", "INFO")
        result = import_dxf(cfg["dxf_path"], lm, unit_scale=scale)
        self._log(f"  Walls={len(result.wall_segments)}  Beams={len(result.beam_segments)}  "
                  f"Cols={len(result.column_points)}  Slabs={len(result.slab_polygons)}  "
                  f"Openings={len(result.opening_polygons)}")

        # 3  Start RAM Concept
        self._log("Starting RAM Concept…", "INFO")
        concept = Concept.start_concept(headless=bool(cfg["headless"]))
        try:
            model = concept.new_model()

            # Design code and structure type
            dc_str   = DESIGN_CODES[cfg["design_code"]]
            st_str   = STRUCTURE_TYPES[cfg["structure_type"]]
            dc_enum  = getattr(DesignCode,    dc_str)
            st_enum  = getattr(StructureType, st_str)
            model.setup_new_model(dc_enum, st_enum)
            self._log(f"  Design code: {cfg['design_code']},  Structure: {cfg['structure_type']}")

            # Units (save and restore)
            units = model.units
            signs = model.signs
            units.set_SI_user_units()
            saved_units = units.get_units()
            signs.set_standard_signs()
            saved_signs = signs.get_signs()

            # Concrete
            fc   = float(cfg["fc_mpa"])
            name = cfg["concrete_name"].strip() or f"{int(fc)} MPa"
            self._log(f"  Adding concrete mix: {name}  f'c={fc} MPa", "INFO")
            add_concrete_mix(model, fc_mpa=fc, name=name)

            # Build
            self._log("--- Building structure ---", "INFO")
            summary: BuildSummary = build_structure(
                model, result, lm,
                log=lambda m: self._log(m),
                mesh_after=bool(cfg["mesh_after"]),
            )

            # Save
            out = cfg["output_cpt_path"].strip()
            self._log(f"Saving to: {out}", "INFO")
            model.save_file(out)
            self._log(f"✓ Saved successfully: {out}", "SUCCESS")

            # Summary
            self._log(
                f"\n✓ Import complete: "
                f"  {summary.slabs_created} slabs  "
                f"| {summary.walls_created} walls  "
                f"| {summary.columns_created} columns  "
                f"| {summary.beams_created} beams  "
                f"| {summary.openings_created} openings  "
                f"| {summary.drop_caps_created} drop-caps  "
                f"| {summary.drop_panels_created} drop-panels",
                "SUCCESS",
            )
            if summary.errors:
                self._log(f"  ⚠  {len(summary.errors)} build error(s) – see log above.", "WARN")

        finally:
            self._log("Shutting down RAM Concept…", "INFO")
            concept.shut_down()
            self._log("Done.", "INFO")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
