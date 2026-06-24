"""
materials_tab.py
================
Tab for concrete and PT system material configuration.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.theme import *
from gui.widgets import styled_entry, styled_check, styled_label, section_label
from core.models import ConcreteSpec, PTSystemSpec


class MaterialsTab(tk.Frame):
    """Materials tab — Concrete Data + PT System Data."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C_PANEL)
        self.app = app
        self._build()

    def _build(self):
        # Scrollable frame
        canvas = tk.Canvas(self, bg=C_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        inner = tk.Frame(canvas, bg=C_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # ── Concrete Data ─────────────────────────────────────────────────────
        section_label(inner, "  Concrete Data").pack(fill="x", padx=16, pady=(12, 0))
        cf = tk.Frame(inner, bg=C_PANEL)
        cf.pack(fill="x", padx=16, pady=6)

        concrete_fields = [
            ("Concrete Name:", self.app.v_conc_name),
            ("fc_final (MPa):", self.app.v_fc_final),
            ("fc_initial (MPa):", self.app.v_fc_initial),
            ("Poisson's Ratio:", self.app.v_poisson),
            ("Unit Mass (kg/m³):", self.app.v_unit_mass),
            ("Unit Mass for Loads (kg/m³):", self.app.v_unit_mass_loads),
        ]
        for r, (label, var) in enumerate(concrete_fields):
            tk.Label(cf, text=label, bg=C_PANEL, fg=C_MUTED, width=30, anchor="w").grid(
                row=r, column=0, sticky="w", padx=8, pady=3
            )
            styled_entry(cf, var, width=20).grid(row=r, column=1, sticky="w", padx=4)

        r = len(concrete_fields)
        styled_check(cf, "Use Code Ec", self.app.v_use_code_ec).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )

        # ── PT System Data (info-only for now) ─────────────────────────────────
        section_label(inner, "  PT System Data (Future Extension)").pack(
            fill="x", padx=16, pady=(16, 0)
        )
        pf = tk.Frame(inner, bg=C_PANEL)
        pf.pack(fill="x", padx=16, pady=6)

        pt_fields = [
            ("PT Name:", self.app.v_pt_name),
            ("Strand Name:", self.app.v_pt_strand),
            ("Duct Name:", self.app.v_pt_duct),
            ("Anchor Name:", self.app.v_pt_anchor),
            ("Aps (m²):", self.app.v_pt_aps),
            ("Eps (MPa):", self.app.v_pt_eps),
            ("Fse (MPa):", self.app.v_pt_fse),
            ("Fpy (MPa):", self.app.v_pt_fpy),
            ("Fpu (MPa):", self.app.v_pt_fpu),
            ("Duct Width (m):", self.app.v_pt_duct_w),
            ("Duct Height (m):", self.app.v_pt_duct_h),
            ("Strands per Duct:", self.app.v_pt_strands),
            ("System Type:", self.app.v_pt_sys_type),
            ("Duct Shape:", self.app.v_pt_duct_shape),
            ("Duct Type:", self.app.v_pt_duct_type),
            ("Anchor Type:", self.app.v_pt_anchor_type),
        ]
        for r, (label, var) in enumerate(pt_fields):
            tk.Label(pf, text=label, bg=C_PANEL, fg=C_MUTED, width=30, anchor="w").grid(
                row=r, column=0, sticky="w", padx=8, pady=2
            )
            styled_entry(pf, var, width=20).grid(row=r, column=1, sticky="w", padx=4)

    def get_concrete_spec(self) -> ConcreteSpec:
        """Read concrete spec from GUI fields."""

        def fval(var, default=0.0):
            try:
                return float(var.get())
            except (ValueError, TypeError):
                return default

        return ConcreteSpec(
            name=self.app.v_conc_name.get() or "45 MPa",
            fc_final=fval(self.app.v_fc_final, 45.0),
            fc_initial=fval(self.app.v_fc_initial, 30.0),
            poissons_ratio=fval(self.app.v_poisson, 0.2),
            unit_mass=fval(self.app.v_unit_mass, 2450),
            unit_mass_for_loads=fval(self.app.v_unit_mass_loads, 2500),
            use_code_Ec=self.app.v_use_code_ec.get(),
        )

    def get_pt_spec(self) -> PTSystemSpec:
        """Read PT spec from GUI fields."""

        def fval(var, default=0.0):
            try:
                return float(var.get())
            except (ValueError, TypeError):
                return default

        return PTSystemSpec(
            pt_name=self.app.v_pt_name.get(),
            strand_name=self.app.v_pt_strand.get(),
            duct_name=self.app.v_pt_duct.get(),
            anchor_name=self.app.v_pt_anchor.get(),
            aps=fval(self.app.v_pt_aps, 100e-6),
            eps=fval(self.app.v_pt_eps, 195_000.0),
            fse=fval(self.app.v_pt_fse, 1_100.0),
            fpy=fval(self.app.v_pt_fpy, 1_564.0),
            fpu=fval(self.app.v_pt_fpu, 1_840.0),
            duct_width=fval(self.app.v_pt_duct_w, 70e-3),
            duct_height=fval(self.app.v_pt_duct_h, 35e-3),
            strands_per_duct=int(fval(self.app.v_pt_strands, 4)),
            system_type=self.app.v_pt_sys_type.get(),
            duct_shape=self.app.v_pt_duct_shape.get(),
            duct_type=self.app.v_pt_duct_type.get(),
            anchor_type=self.app.v_pt_anchor_type.get(),
        )
