"""
loads_tab.py
============
Tab for load types — Line Load, Area Load, Point Load.
Each has an editable table matching the reference tool's format:
  layer_name, elevation_dead, value_dead, elevation_live, value_live, live_load_type
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.theme import *
from gui.widgets import EditableTable, styled_label
from core.constants import LOAD_ROLES, LIVE_LOAD_TYPES
from core.models import LineLoadSpec, AreaLoadSpec, PointLoadSpec, LoadValues

# ── Per-role load table columns (units differ by load type) ──────────────────

_LIVE_LOAD_TYPE_COL = {
    "key": "live_load_type",
    "label": "Live Load Type",
    "width": 120,
    "edit_type": "combo",
    "values": LIVE_LOAD_TYPES,
}

LINELOAD_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "elevation_dead", "label": "Elev. Dead (m)", "width": 110},
    {"key": "value_dead", "label": "Dead (Fx,Fy,Fz kN/m; Mx,My kN\u00b7m/m)", "width": 260},
    {"key": "elevation_live", "label": "Elev. Live (m)", "width": 110},
    {"key": "value_live", "label": "Live (Fx,Fy,Fz kN/m; Mx,My kN\u00b7m/m)", "width": 260},
    _LIVE_LOAD_TYPE_COL,
]

AREALOAD_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "elevation_dead", "label": "Elev. Dead (m)", "width": 110},
    {"key": "value_dead", "label": "Dead (Fx,Fy,Fz kN/m\u00b2; Mx,My kN\u00b7m/m\u00b2)", "width": 270},
    {"key": "elevation_live", "label": "Elev. Live (m)", "width": 110},
    {"key": "value_live", "label": "Live (Fx,Fy,Fz kN/m\u00b2; Mx,My kN\u00b7m/m\u00b2)", "width": 270},
    _LIVE_LOAD_TYPE_COL,
]

POINTLOAD_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "elevation_dead", "label": "Elev. Dead (m)", "width": 110},
    {"key": "value_dead", "label": "Dead (Fx,Fy,Fz kN; Mx,My kN\u00b7m)", "width": 250},
    {"key": "elevation_live", "label": "Elev. Live (m)", "width": 110},
    {"key": "value_live", "label": "Live (Fx,Fy,Fz kN; Mx,My kN\u00b7m)", "width": 250},
    _LIVE_LOAD_TYPE_COL,
]

ROLE_LOAD_COLUMNS: dict[str, list[dict]] = {
    "lineload": LINELOAD_COLUMNS,
    "areaload": AREALOAD_COLUMNS,
    "pointload": POINTLOAD_COLUMNS,
}

ROLE_DISPLAY = {
    "lineload": "Line Load",
    "areaload": "Area Load",
    "pointload": "Point Load",
}

ROLE_UNIT_HINT = {
    "lineload": "Forces: kN/m  |  Moments: kN\u00b7m/m",
    "areaload": "Forces: kN/m\u00b2  |  Moments: kN\u00b7m/m\u00b2",
    "pointload": "Forces: kN  |  Moments: kN\u00b7m",
}


class LoadsTab(tk.Frame):
    """Loads tab with inner sub-tabs for Line, Area, and Point loads."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C_PANEL)
        self.app = app
        self.tables: dict[str, EditableTable] = {}
        self._build()

    def _build(self):
        nb = ttk.Notebook(self, style="Inner.TNotebook")
        nb.pack(fill="both", expand=True, padx=4, pady=4)

        for role in LOAD_ROLES:
            display_name = ROLE_DISPLAY.get(role, role)
            unit_hint = ROLE_UNIT_HINT.get(role, "")
            col_defs = ROLE_LOAD_COLUMNS.get(role, POINTLOAD_COLUMNS)
            frame = tk.Frame(nb, bg=C_PANEL)
            nb.add(frame, text=f"  {display_name}  ")

            # Info label with unit hint
            styled_label(
                frame,
                f"Double-click cells to edit. "
                f"Values format: Fx,Fy,Fz,Mx,My  (e.g. 0,0,5.0,0,0 downward).  "
                f"Units \u2014 {unit_hint}",
                fg=C_TIP,
                font=("Segoe UI", 8, "italic"),
            ).pack(fill="x", padx=8, pady=(6, 2))

            table = EditableTable(frame, col_defs)
            table.pack(fill="both", expand=True, padx=8, pady=4)
            self.tables[role] = table

    def populate_from_instances(self, instances: list):
        """Fill load tables from LayerInstance objects."""
        for table in self.tables.values():
            table.clear()

        for li in instances:
            if li.role not in self.tables:
                continue
            table = self.tables[li.role]
            row_data = self._spec_to_row(li)
            table.insert_row(row_data)

    def _spec_to_row(self, li) -> dict:
        """Convert a load LayerInstance to a table row."""
        spec = li.spec
        row = {"layer_name": li.layer_name}

        if hasattr(spec, "elevation_dead"):
            row["elevation_dead"] = str(spec.elevation_dead)
        if hasattr(spec, "value_dead"):
            row["value_dead"] = spec.value_dead.to_string()
        if hasattr(spec, "elevation_live"):
            row["elevation_live"] = str(spec.elevation_live)
        if hasattr(spec, "value_live"):
            row["value_live"] = spec.value_live.to_string()
        if hasattr(spec, "live_load_type"):
            row["live_load_type"] = spec.live_load_type

        return row

    def collect_to_instances(self, instances: list):
        """Write table edits back to load LayerInstance specs."""
        for li in instances:
            if li.role not in self.tables:
                continue
            table = self.tables[li.role]
            for row in table.get_all_data():
                if row.get("layer_name") != li.layer_name:
                    continue
                self._row_to_spec(li, row)
                break

    def _row_to_spec(self, li, row: dict):
        """Update a load spec from a table row."""
        spec = li.spec
        if spec is None:
            return

        try:
            spec.elevation_dead = float(row.get("elevation_dead", 0))
        except (ValueError, TypeError):
            pass

        try:
            spec.value_dead = LoadValues.from_string(row.get("value_dead", "0,0,0,0,0"))
        except Exception:
            pass

        try:
            spec.elevation_live = float(row.get("elevation_live", 0))
        except (ValueError, TypeError):
            pass

        try:
            spec.value_live = LoadValues.from_string(row.get("value_live", "0,0,0,0,0"))
        except Exception:
            pass

        spec.live_load_type = row.get("live_load_type", "Reducible")
