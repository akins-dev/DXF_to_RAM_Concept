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
)
from core.constants import DESIGN_CODES, STRUCTURE_TYPES, UNIT_SCALES


class FilesTab(tk.Frame):
    """Files & Settings tab."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C_PANEL)
        self.app = app
        self._build()

    def _build(self):
        # ── File Paths ────────────────────────────────────────────────────────
        section_label(self, "  File Paths").pack(fill="x", padx=16, pady=(12, 0))
        f = tk.Frame(self, bg=C_PANEL)
        f.pack(fill="x", padx=16, pady=6)
        f.columnconfigure(1, weight=1)

        rows = [
            ("DXF input file:", self.app.v_dxf, self._browse_dxf),
            ("Output .cpt file:", self.app.v_output, self._browse_cpt),
            ("RAM Concept API folder:", self.app.v_api_path, self._browse_api),
        ]
        for r, (label, var, cmd) in enumerate(rows):
            tk.Label(f, text=label, bg=C_PANEL, fg=C_MUTED, width=28, anchor="w").grid(
                row=r, column=0, sticky="w", padx=8, pady=3
            )
            styled_entry(f, var, width=42).grid(row=r, column=1, sticky="we", padx=4)
            styled_btn(f, "…", cmd).grid(row=r, column=2, padx=4)

        # ── Units ─────────────────────────────────────────────────────────────
        section_label(self, "  Units & Scale").pack(fill="x", padx=16, pady=(12, 0))
        uf = tk.Frame(self, bg=C_PANEL)
        uf.pack(fill="x", padx=16, pady=6)

        tk.Label(uf, text="DXF drawing units:", bg=C_PANEL, fg=C_MUTED).grid(
            row=0, column=0, sticky="w", padx=8
        )
        unit_dd = ttk.Combobox(
            uf,
            textvariable=self.app.v_unit_key,
            values=list(UNIT_SCALES.keys()),
            width=24,
            state="readonly",
            style="Dark.TCombobox",
        )
        unit_dd.grid(row=0, column=1, padx=4, sticky="w")
        unit_dd.bind("<<ComboboxSelected>>", lambda e: self._on_unit_change())

        self._custom_lbl = tk.Label(uf, text="Custom scale:", bg=C_PANEL, fg=C_MUTED)
        self._custom_ent = styled_entry(uf, self.app.v_unit_custom, width=10)
        self._on_unit_change()

        # ── Design Code ───────────────────────────────────────────────────────
        section_label(self, "  Design Code & Structure Type").pack(
            fill="x", padx=16, pady=(12, 0)
        )
        df = tk.Frame(self, bg=C_PANEL)
        df.pack(fill="x", padx=16, pady=6)

        tk.Label(df, text="Design code:", bg=C_PANEL, fg=C_MUTED).grid(
            row=0, column=0, sticky="w", padx=8
        )
        ttk.Combobox(
            df,
            textvariable=self.app.v_design_code,
            values=list(DESIGN_CODES.keys()),
            width=26,
            state="readonly",
            style="Dark.TCombobox",
        ).grid(row=0, column=1, padx=4, sticky="w")

        tk.Label(df, text="Structure type:", bg=C_PANEL, fg=C_MUTED).grid(
            row=1, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Combobox(
            df,
            textvariable=self.app.v_struct_type,
            values=list(STRUCTURE_TYPES.keys()),
            width=26,
            state="readonly",
            style="Dark.TCombobox",
        ).grid(row=1, column=1, padx=4, sticky="w")

        # ── Options ───────────────────────────────────────────────────────────
        section_label(self, "  Options").pack(fill="x", padx=16, pady=(12, 0))
        of = tk.Frame(self, bg=C_PANEL)
        of.pack(fill="x", padx=16, pady=6)
        styled_check(of, "Generate mesh after import", self.app.v_mesh_after).pack(
            side="left", padx=8
        )
        styled_check(of, "Run RAM Concept headless", self.app.v_headless).pack(
            side="left", padx=8
        )

        # ── Notes ─────────────────────────────────────────────────────────────
        section_label(self, "  DXF Drawing Rules").pack(fill="x", padx=16, pady=(12, 0))
        notes = tk.Frame(self, bg=C_PANEL)
        notes.pack(fill="x", padx=16, pady=6)
        note_text = (
            "REMEMBER:\n"
            "• DXF must be in the selected drawing units\n"
            "• Layer names must contain element keywords: "
            "slab, beam, column, wall, opening, lineload, areaload, pointload\n"
            "• Columns: polyline for any shape, circle for circular\n"
            "• Beams & walls: line/polyline at centerline\n"
            "• Slabs & openings: closed polyline\n"
            "• Line loads: line/polyline\n"
            "• Area loads: closed polyline\n"
            "• Point loads: point entity"
        )
        tk.Label(
            notes,
            text=note_text,
            bg=C_PANEL,
            fg=C_WARN,
            font=("Segoe UI", 8),
            justify="left",
            anchor="w",
            wraplength=700,
        ).pack(fill="x")

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
