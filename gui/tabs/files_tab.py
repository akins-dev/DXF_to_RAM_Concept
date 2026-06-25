"""
files_tab.py
============
Tab 1: DXF file selection, output path, RAM API path,
design code, structure type, units, and options.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path

from gui.theme import *
from gui.widgets import (
    styled_entry,
    styled_check,
    styled_label,
    styled_btn,
    section_label,
    panel,
    panel_title,
    field_row,
    notice,
)
from core.constants import DESIGN_CODES, STRUCTURE_TYPES, UNIT_SCALES


class FilesTab(tk.Frame):
    """Files & Settings tab."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C_PANEL)
        self.app = app
        self._build()

    def _build(self):
        outer = tk.Frame(self, bg=C_PANEL)
        outer.pack(fill="both", expand=True, padx=14, pady=12)
        outer.columnconfigure(0, weight=3)
        outer.columnconfigure(1, weight=2)

        left = tk.Frame(outer, bg=C_PANEL)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = tk.Frame(outer, bg=C_PANEL)
        right.grid(row=0, column=1, sticky="nsew")

        # Project files
        file_panel = panel(left)
        file_panel.pack(fill="x", pady=(0, 10))
        panel_title(
            file_panel,
            "Project Files",
            "Choose the DXF source, output Concept file, and RAM Concept API Python folder.",
        ).pack(fill="x", padx=14, pady=(12, 8))
        f = tk.Frame(file_panel, bg=C_SURFACE)
        f.pack(fill="x", padx=14, pady=(0, 14))
        f.columnconfigure(1, weight=1)

        rows = [
            ("DXF input", self.app.v_dxf, self._browse_dxf, "Browse"),
            ("Output .cpt", self.app.v_output, self._browse_cpt, "Save As"),
            ("RAM API folder", self.app.v_api_path, self._browse_api, "Browse"),
        ]
        for r, (label, var, cmd, btn_text) in enumerate(rows):
            tk.Label(f, text=label, bg=C_SURFACE, fg=C_MUTED, anchor="w").grid(
                row=r, column=0, sticky="w", padx=(0, 10), pady=5
            )
            styled_entry(f, var, width=42).grid(row=r, column=1, sticky="we", pady=5)
            styled_btn(f, btn_text, cmd).grid(row=r, column=2, padx=(8, 0), pady=5)

        # Model setup
        model_panel = panel(left)
        model_panel.pack(fill="x", pady=(0, 10))
        panel_title(
            model_panel,
            "Model Setup",
            "Match the drawing units before scanning. The importer converts geometry to RAM Concept meters.",
        ).pack(fill="x", padx=14, pady=(12, 8))
        mf = tk.Frame(model_panel, bg=C_SURFACE)
        mf.pack(fill="x", padx=14, pady=(0, 14))

        unit_dd = ttk.Combobox(
            mf,
            textvariable=self.app.v_unit_key,
            values=list(UNIT_SCALES.keys()),
            width=24,
            state="readonly",
            style="Dark.TCombobox",
        )
        field_row(mf, 0, "DXF units", unit_dd)
        unit_dd.bind("<<ComboboxSelected>>", lambda e: self._on_unit_change())

        self._custom_lbl = tk.Label(mf, text="Custom scale", bg=C_SURFACE, fg=C_MUTED)
        self._custom_ent = styled_entry(mf, self.app.v_unit_custom, width=12)
        self._on_unit_change()

        self._code_dd = ttk.Combobox(
            mf,
            textvariable=self.app.v_design_code,
            values=list(DESIGN_CODES.keys()),
            width=34,
            state="readonly",
            style="Dark.TCombobox",
        )
        field_row(mf, 2, "Design code", self._code_dd)

        self._struct_dd = ttk.Combobox(
            mf,
            textvariable=self.app.v_struct_type,
            values=list(STRUCTURE_TYPES.keys()),
            width=34,
            state="readonly",
            style="Dark.TCombobox",
        )
        field_row(mf, 3, "Structure type", self._struct_dd)

        # Options
        option_panel = panel(right)
        option_panel.pack(fill="x", pady=(0, 10))
        panel_title(option_panel, "Run Options", "Control how RAM Concept is launched and finalized.").pack(
            fill="x", padx=14, pady=(12, 8)
        )
        of = tk.Frame(option_panel, bg=C_SURFACE)
        of.pack(fill="x", padx=14, pady=(0, 14))
        styled_check(of, "Generate mesh after import", self.app.v_mesh_after).pack(
            anchor="w", pady=3
        )
        styled_check(of, "Run RAM Concept headless", self.app.v_headless).pack(
            anchor="w", pady=3
        )

        # Drawing rules
        rules_panel = panel(right)
        rules_panel.pack(fill="both", expand=True)
        panel_title(rules_panel, "DXF Drawing Rules", "Layer names drive classification; geometry type drives extraction.").pack(
            fill="x", padx=14, pady=(12, 8)
        )
        rules = (
            "Required layer keywords: slab, beam, column, wall, opening, lineload, areaload, pointload\n"
            "Columns: polyline for any shape, circle for circular\n"
            "Beams and walls: line/polyline at centerline\n"
            "Slabs, openings, area loads: closed polyline\n"
            "Point loads: POINT entity"
        )
        notice(rules_panel, rules, "warn").pack(fill="x", padx=14, pady=(0, 14))

    def _on_unit_change(self):
        key = self.app.v_unit_key.get()
        if key == "Custom…":
            self._custom_lbl.grid(row=1, column=0, sticky="w", padx=8, pady=4)
            self._custom_ent.grid(row=1, column=1, padx=4, sticky="w")
        else:
            try:
                self._custom_lbl.grid_remove()
                self._custom_ent.grid_remove()
            except Exception:
                pass

    def _browse_dxf(self):
        p = filedialog.askopenfilename(
            filetypes=[("DXF files", "*.dxf"), ("All", "*.*")]
        )
        if p:
            self.app.v_dxf.set(p)

    def _browse_cpt(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".cpt",
            filetypes=[("RAM Concept", "*.cpt"), ("All", "*.*")],
        )
        if p:
            self.app.v_output.set(p)

    def _browse_api(self):
        p = filedialog.askdirectory(title="Select RAM Concept 'python' folder")
        if p:
            self.app.v_api_path.set(p)
            # Trigger enum discovery from the real API
            self.app._try_discover_api_enums()

    def refresh_dropdowns(self):
        """Refresh design code and structure type dropdowns with current values."""
        code_keys = list(DESIGN_CODES.keys())
        struct_keys = list(STRUCTURE_TYPES.keys())

        self._code_dd["values"] = code_keys
        self._struct_dd["values"] = struct_keys

        # If current selection is not in the new list, pick the first
        if self.app.v_design_code.get() not in code_keys and code_keys:
            self.app.v_design_code.set(code_keys[0])
        if self.app.v_struct_type.get() not in struct_keys and struct_keys:
            self.app.v_struct_type.set(struct_keys[0])
