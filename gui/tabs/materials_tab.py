"""
materials_tab.py
================
Tab for concrete and optional post-tensioning material configuration.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.theme import *
from gui.widgets import (
    field_row,
    notice,
    panel,
    panel_title,
    styled_check,
    styled_entry,
)
from core.models import ConcreteSpec, PTSystemSpec


SYSTEM_TYPES = ["BONDED", "UNBONDED"]
DUCT_SHAPES = ["ROUND", "FLAT", "OVAL"]
DUCT_TYPES = [
    "CORRUGATED_PLASTIC",
    "SMOOTH_PLASTIC",
    "CORRUGATED_STEEL",
    "SMOOTH_STEEL",
    "TIGHTLY_SHEATHED",
]
ANCHOR_TYPES = [
    "MONOSTRAND",
    "FLAT_MULTI_PLANE",
    "FLAT_SINGLE_PLANE",
    "CIRCULAR_MULTI_PLANE",
    "CIRCULAR_SINGLE_PLANE",
    "SQUARE_MULTI_PLANE",
    "SQUARE_SINGLE_PLANE",
]


class MaterialsTab(tk.Frame):
    """Materials tab: concrete plus optional PT definition objects."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C_PANEL)
        self.app = app
        self._pt_master_widgets: list[tk.Widget] = []
        self._strand_widgets: list[tk.Widget] = []
        self._duct_widgets: list[tk.Widget] = []
        self._anchor_widgets: list[tk.Widget] = []
        self._build()

    def _build(self):
        canvas = tk.Canvas(self, bg=C_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        inner = tk.Frame(canvas, bg=C_PANEL)
        inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_inner(event):
            canvas.itemconfigure(inner_window, width=event.width)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_mousewheel(_event=None):
            canvas.bind_all("<MouseWheel>", on_mousewheel)

        def unbind_mousewheel(_event=None):
            canvas.unbind_all("<MouseWheel>")

        inner.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_inner)
        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)

        body = tk.Frame(inner, bg=C_PANEL)
        body.pack(fill="both", expand=True, padx=14, pady=12)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        concrete = panel(body)
        concrete.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        self._build_concrete_panel(concrete)

        pt_system = panel(body)
        pt_system.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        self._build_pt_system_panel(pt_system)

        strand = panel(body)
        strand.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        self._build_strand_panel(strand)

        duct = panel(body)
        duct.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        self._build_duct_panel(duct)

        anchor = panel(body)
        anchor.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
        self._build_anchor_panel(anchor)

        for var in (
            self.app.v_use_pt_system,
            self.app.v_use_pt_strand,
            self.app.v_use_pt_duct,
            self.app.v_use_pt_anchor,
        ):
            var.trace_add("write", lambda *_: self._refresh_pt_states())
        self._refresh_pt_states()

    def _build_concrete_panel(self, parent):
        panel_title(parent, "Concrete", "Concrete mix used by generated slabs, beams, columns, and walls.").pack(
            fill="x", padx=14, pady=(12, 8)
        )
        grid = tk.Frame(parent, bg=parent.cget("bg"))
        grid.pack(fill="x", padx=14, pady=(0, 12))
        fields = [
            ("Name", styled_entry(grid, self.app.v_conc_name, width=22), ""),
            ("fc final", styled_entry(grid, self.app.v_fc_final, width=22), "MPa"),
            ("fc initial", styled_entry(grid, self.app.v_fc_initial, width=22), "MPa"),
            ("Poisson ratio", styled_entry(grid, self.app.v_poisson, width=22), ""),
            ("Unit mass", styled_entry(grid, self.app.v_unit_mass, width=22), "kg/m3"),
            ("Load mass", styled_entry(grid, self.app.v_unit_mass_loads, width=22), "kg/m3"),
        ]
        for r, (label, widget, unit) in enumerate(fields):
            field_row(grid, r, label, widget, unit)
        styled_check(grid, "Use code Ec", self.app.v_use_code_ec).grid(
            row=len(fields), column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

    def _build_pt_system_panel(self, parent):
        head = tk.Frame(parent, bg=parent.cget("bg"))
        head.pack(fill="x", padx=14, pady=(12, 8))
        panel_title(
            head,
            "Post-Tensioning System",
            "Creates the RAM Concept PTSystem that links the strand, duct, and anchor definitions.",
        ).pack(side="left", fill="x", expand=True)
        styled_check(head, "Use PT", self.app.v_use_pt_system).pack(side="right")

        grid = tk.Frame(parent, bg=parent.cget("bg"))
        grid.pack(fill="x", padx=14, pady=(0, 12))
        self._add_pt_row(self._pt_master_widgets, grid, 0, "PT name", styled_entry(grid, self.app.v_pt_name, width=24))
        self._add_pt_row(self._pt_master_widgets, grid, 1, "Final effective stress", styled_entry(grid, self.app.v_pt_fse, width=24), "MPa")
        self._add_pt_row(self._pt_master_widgets, grid, 2, "Long-term losses", styled_entry(grid, self.app.v_pt_long_losses, width=24), "MPa")
        self._add_pt_row(self._pt_master_widgets, grid, 3, "Min curvature radius", styled_entry(grid, self.app.v_pt_min_radius, width=24), "m")
        notice(parent, "Fse is only used by RAM Concept when tendons are not modeled with jacks.", "info").pack(
            fill="x", padx=14, pady=(0, 12)
        )

    def _build_strand_panel(self, parent):
        self._section_header(parent, "Strand Material", self.app.v_use_pt_strand, "Create/update")
        grid = tk.Frame(parent, bg=parent.cget("bg"))
        grid.pack(fill="x", padx=14, pady=(0, 12))
        fields = [
            ("Strand name", styled_entry(grid, self.app.v_pt_strand, width=24), ""),
            ("Area Aps", styled_entry(grid, self.app.v_pt_aps, width=24), "mm2"),
            ("Elastic modulus Eps", styled_entry(grid, self.app.v_pt_eps, width=24), "MPa"),
            ("Yield strength Fpy", styled_entry(grid, self.app.v_pt_fpy, width=24), "MPa"),
            ("Ultimate strength Fpu", styled_entry(grid, self.app.v_pt_fpu, width=24), "MPa"),
        ]
        for r, (label, widget, unit) in enumerate(fields):
            self._add_pt_row(self._strand_widgets, grid, r, label, widget, unit)

    def _build_duct_panel(self, parent):
        self._section_header(parent, "Duct System", self.app.v_use_pt_duct, "Create/update")
        grid = tk.Frame(parent, bg=parent.cget("bg"))
        grid.pack(fill="x", padx=14, pady=(0, 12))
        fields = [
            ("Duct name", styled_entry(grid, self.app.v_pt_duct, width=24), ""),
            ("System type", self._combo(grid, self.app.v_pt_sys_type, SYSTEM_TYPES), ""),
            ("Duct shape", self._combo(grid, self.app.v_pt_duct_shape, DUCT_SHAPES), ""),
            ("Duct type", self._combo(grid, self.app.v_pt_duct_type, DUCT_TYPES), ""),
            ("Duct width", styled_entry(grid, self.app.v_pt_duct_w, width=24), "mm"),
            ("Duct height", styled_entry(grid, self.app.v_pt_duct_h, width=24), "mm"),
            ("Strands per duct", styled_entry(grid, self.app.v_pt_strands, width=24), ""),
            ("Angular friction", styled_entry(grid, self.app.v_pt_angular_friction, width=24), ""),
            ("Wobble friction", styled_entry(grid, self.app.v_pt_wobble_friction, width=24), ""),
        ]
        for r, (label, widget, unit) in enumerate(fields):
            self._add_pt_row(self._duct_widgets, grid, r, label, widget, unit)

    def _build_anchor_panel(self, parent):
        self._section_header(parent, "Anchor System", self.app.v_use_pt_anchor, "Create/update")
        grid = tk.Frame(parent, bg=parent.cget("bg"))
        grid.pack(fill="x", padx=14, pady=(0, 12))
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(4, weight=1)
        fields = [
            ("Anchor name", styled_entry(grid, self.app.v_pt_anchor, width=24), ""),
            ("Anchor type", self._combo(grid, self.app.v_pt_anchor_type, ANCHOR_TYPES), ""),
            ("Jack stress", styled_entry(grid, self.app.v_pt_jack_stress, width=24), "MPa"),
            ("Anchor friction", styled_entry(grid, self.app.v_pt_anchor_friction, width=24), ""),
            ("Seating distance", styled_entry(grid, self.app.v_pt_seating_distance, width=24), "mm"),
        ]
        for r, (label, widget, unit) in enumerate(fields):
            column_offset = 0 if r < 3 else 3
            row = r if r < 3 else r - 3
            bg = grid.cget("bg")
            tk.Label(grid, text=label, bg=bg, fg=C_MUTED, anchor="w").grid(
                row=row, column=column_offset, sticky="w", padx=(0, 10), pady=5
            )
            widget.grid(row=row, column=column_offset + 1, sticky="we", pady=5)
            if unit:
                tk.Label(grid, text=unit, bg=bg, fg=C_MUTED).grid(
                    row=row, column=column_offset + 2, sticky="w", padx=(8, 16), pady=5
                )
            self._anchor_widgets.append(widget)

    def _section_header(self, parent, title, variable, toggle_text):
        head = tk.Frame(parent, bg=parent.cget("bg"))
        head.pack(fill="x", padx=14, pady=(12, 8))
        panel_title(head, title).pack(side="left", fill="x", expand=True)
        check = styled_check(head, toggle_text, variable)
        check.pack(side="right")
        self._pt_master_widgets.append(check)

    def _combo(self, parent, variable, values):
        return ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
            style="Dark.TCombobox",
            width=22,
        )

    def _add_pt_row(self, bucket, parent, row, label, widget, unit=""):
        field_row(parent, row, label, widget, unit)
        bucket.append(widget)

    def _set_widgets_state(self, widgets, enabled):
        state = "normal" if enabled else "disabled"
        for widget in widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly" if enabled else "disabled")
            else:
                try:
                    widget.configure(state=state)
                except tk.TclError:
                    pass

    def _refresh_pt_states(self):
        use_pt = self.app.v_use_pt_system.get()
        self._set_widgets_state(self._pt_master_widgets, use_pt)
        self._set_widgets_state(self._strand_widgets, use_pt and self.app.v_use_pt_strand.get())
        self._set_widgets_state(self._duct_widgets, use_pt and self.app.v_use_pt_duct.get())
        self._set_widgets_state(self._anchor_widgets, use_pt and self.app.v_use_pt_anchor.get())

    def get_concrete_spec(self) -> ConcreteSpec:
        """Read concrete spec from GUI fields."""

        def fval(var, default=0.0):
            try:
                return float(var.get())
            except (ValueError, TypeError):
                return default

        return ConcreteSpec(
            name=self.app.v_conc_name.get() or "C45",
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
            use_pt_system=self.app.v_use_pt_system.get(),
            use_strand_material=self.app.v_use_pt_strand.get(),
            use_duct_system=self.app.v_use_pt_duct.get(),
            use_anchor_system=self.app.v_use_pt_anchor.get(),
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
            min_curvature_radius=fval(self.app.v_pt_min_radius, 2.0),
            anchor_friction=fval(self.app.v_pt_anchor_friction, 0.02),
            angular_friction=fval(self.app.v_pt_angular_friction, 0.2),
            jack_stress=fval(self.app.v_pt_jack_stress, 1_564.0),
            seating_distance=fval(self.app.v_pt_seating_distance, 6e-3),
            long_term_losses=fval(self.app.v_pt_long_losses, 150.0),
            wobble_friction=fval(self.app.v_pt_wobble_friction, 0.005),
            system_type=self.app.v_pt_sys_type.get(),
            duct_shape=self.app.v_pt_duct_shape.get(),
            duct_type=self.app.v_pt_duct_type.get(),
            anchor_type=self.app.v_pt_anchor_type.get(),
        )
