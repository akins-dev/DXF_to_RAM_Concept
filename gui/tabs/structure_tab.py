"""
structure_tab.py
================
Tab for structural elements — uses inner sub-tabs for each element type
(Slab, Beam, Column, Wall, Opening, Drop Cap, Drop Panel, Point Support,
Line Support, Area Spring).

Each sub-tab contains an EditableTable populated from the DXF layer scan.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.theme import *
from gui.widgets import EditableTable, styled_label
from core.constants import STRUCTURAL_ROLES

# Column definitions for each structural element type
SLAB_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "priority", "label": "Priority", "width": 80},
    {"key": "thickness", "label": "Thickness (m)", "width": 110},
    {"key": "toc", "label": "TOC (m)", "width": 90},
    {"key": "axis", "label": "Axis (°)", "width": 80},
    {
        "key": "mesh_as_slab",
        "label": "Mesh as Slab",
        "width": 100,
        "edit_type": "check",
    },
]

BEAM_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "width", "label": "Width (m)", "width": 110},
    {"key": "depth", "label": "Thickness/Depth (m)", "width": 140},
    {"key": "toc", "label": "TOC (m)", "width": 90},
    {"key": "priority", "label": "Priority", "width": 80},
    {
        "key": "mesh_as_slab",
        "label": "Mesh as Slab",
        "width": 100,
        "edit_type": "check",
    },
]

COLUMN_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "height", "label": "Height (m)", "width": 90},
    {"key": "stiffness_factor", "label": "Stiffness Factor", "width": 110},
    {"key": "fixed_near", "label": "Fixed Near", "width": 80, "edit_type": "check"},
    {"key": "fixed_far", "label": "Fixed Far", "width": 80, "edit_type": "check"},
    {"key": "roller", "label": "Roller", "width": 70, "edit_type": "check"},
    {"key": "specified_LLR", "label": "Specified LLR", "width": 100},
    {"key": "below_slab", "label": "Below Slab", "width": 80, "edit_type": "check"},
    {"key": "above_slab", "label": "Above Slab", "width": 80, "edit_type": "check"},
    {"key": "compressible", "label": "Compressible", "width": 90, "edit_type": "check"},
]

WALL_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "below_slab", "label": "Below Slab", "width": 80, "edit_type": "check"},
    {"key": "above_slab", "label": "Above Slab", "width": 80, "edit_type": "check"},
    {"key": "compressible", "label": "Compressible", "width": 90, "edit_type": "check"},
    {"key": "height", "label": "Height (m)", "width": 90},
    {"key": "fixed_near", "label": "Fixed Near", "width": 80, "edit_type": "check"},
    {"key": "fixed_far", "label": "Fixed Far", "width": 80, "edit_type": "check"},
    {"key": "shear_wall", "label": "Shear Wall", "width": 80, "edit_type": "check"},
    {"key": "thickness", "label": "Thickness (m)", "width": 110},
    {"key": "specified_LLR", "label": "Specified LLR", "width": 100},
]

OPENING_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 250, "editable": False},
    {"key": "priority", "label": "Priority", "width": 100},
]

RECESS_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "recess_depth", "label": "Recess Depth (m)", "width": 120},
    {"key": "slab_thickness", "label": "Slab Thickness (m)", "width": 130},
    {"key": "priority", "label": "Priority", "width": 80},
    {"key": "mesh_as_slab", "label": "Mesh as Slab", "width": 100, "edit_type": "check"},
]

DROP_CAP_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 180, "editable": False},
    {"key": "thickness", "label": "Thickness (m)", "width": 110},
    {"key": "toc", "label": "TOC (m)", "width": 90},
    {"key": "priority", "label": "Priority", "width": 80},
]

DROP_PANEL_COLUMNS = DROP_CAP_COLUMNS.copy()

POINT_SUPPORT_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 250, "editable": False},
    {"key": "spring_kv", "label": "Spring kv (kN/m)", "width": 130},
]

LINE_SUPPORT_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 250, "editable": False},
    {"key": "spring_kv", "label": "Spring kv (kN/m²)", "width": 130},
]

AREA_SPRING_COLUMNS = [
    {"key": "layer_name", "label": "Layer Name", "width": 200, "editable": False},
    {"key": "kv", "label": "kv (kN/m³)", "width": 120},
    {
        "key": "zero_tension",
        "label": "Zero Tension",
        "width": 100,
        "edit_type": "check",
    },
]


# Map role → (display name, column definitions)
ROLE_TABLE_DEFS: dict[str, tuple[str, list[dict]]] = {
    "slab": ("Slab", SLAB_COLUMNS),
    "beam": ("Beam", BEAM_COLUMNS),
    "column": ("Column", COLUMN_COLUMNS),
    "wall": ("Wall", WALL_COLUMNS),
    "opening": ("Opening", OPENING_COLUMNS),
    "drop_cap": ("Drop Cap", DROP_CAP_COLUMNS),
    "drop_panel": ("Drop Panel", DROP_PANEL_COLUMNS),
    "recess": ("Recess", RECESS_COLUMNS),
    "point_support": ("Point Support", POINT_SUPPORT_COLUMNS),
    "line_support": ("Line Support", LINE_SUPPORT_COLUMNS),
    "area_spring": ("Area Spring", AREA_SPRING_COLUMNS),
}


class StructureTab(tk.Frame):
    """Structural elements tab with inner sub-tabs per element type."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C_PANEL)
        self.app = app
        self.tables: dict[str, EditableTable] = {}
        self._build()

    def _build(self):
        nb = ttk.Notebook(self, style="Inner.TNotebook")
        nb.pack(fill="both", expand=True, padx=4, pady=4)

        for role in STRUCTURAL_ROLES:
            if role not in ROLE_TABLE_DEFS:
                continue
            display_name, col_defs = ROLE_TABLE_DEFS[role]
            frame = tk.Frame(nb, bg=C_PANEL)
            nb.add(frame, text=f"  {display_name}  ")

            # Info label
            styled_label(
                frame,
                f"Properties for {display_name} layers. "
                f"Double-click cells to edit. Boolean: 1=True, 0=False.",
                fg=C_TIP,
                font=("Segoe UI", 8, "italic"),
            ).pack(fill="x", padx=8, pady=(6, 2))

            table = EditableTable(frame, col_defs)
            table.pack(fill="both", expand=True, padx=8, pady=4)
            table.set_on_change(
                lambda item, col, val, r=role: self._on_cell_change(r, item, col, val)
            )
            self.tables[role] = table

    def populate_from_instances(self, instances: list):
        """Fill tables from a list of LayerInstance objects."""
        # Clear all tables first
        for table in self.tables.values():
            table.clear()

        for li in instances:
            if li.role not in self.tables:
                continue
            table = self.tables[li.role]
            row_data = self._spec_to_row(li)
            table.insert_row(row_data)

    def _spec_to_row(self, li) -> dict:
        """Convert a LayerInstance's spec to a row dict."""
        spec = li.spec
        row = {"layer_name": li.layer_name}

        if hasattr(spec, "thickness"):
            row["thickness"] = str(spec.thickness)
        if hasattr(spec, "toc"):
            row["toc"] = str(spec.toc)
        if hasattr(spec, "recess_depth"):
            row["recess_depth"] = str(spec.recess_depth)
        if hasattr(spec, "slab_thickness"):
            row["slab_thickness"] = str(spec.slab_thickness)
        if hasattr(spec, "priority"):
            row["priority"] = str(spec.priority)
        if hasattr(spec, "axis"):
            row["axis"] = str(spec.axis)
        if hasattr(spec, "mesh_as_slab"):
            row["mesh_as_slab"] = "1" if spec.mesh_as_slab else "0"
        if hasattr(spec, "width"):
            row["width"] = str(spec.width)
        if hasattr(spec, "depth"):
            row["depth"] = str(spec.depth)
        if hasattr(spec, "height"):
            row["height"] = str(spec.height)
        if hasattr(spec, "stiffness_factor"):
            row["stiffness_factor"] = str(spec.stiffness_factor)
        if hasattr(spec, "fixed_near"):
            row["fixed_near"] = "1" if spec.fixed_near else "0"
        if hasattr(spec, "fixed_far"):
            row["fixed_far"] = "1" if spec.fixed_far else "0"
        if hasattr(spec, "roller"):
            row["roller"] = "1" if spec.roller else "0"
        if hasattr(spec, "below_slab"):
            row["below_slab"] = "1" if spec.below_slab else "0"
        if hasattr(spec, "above_slab"):
            row["above_slab"] = "1" if spec.above_slab else "0"
        if hasattr(spec, "compressible"):
            row["compressible"] = "1" if spec.compressible else "0"
        if hasattr(spec, "shear_wall"):
            row["shear_wall"] = "1" if spec.shear_wall else "0"
        if hasattr(spec, "use_specified_LLR"):
            row["specified_LLR"] = str(spec.specified_LLR)
        if hasattr(spec, "spring_kv"):
            row["spring_kv"] = str(spec.spring_kv)
        if hasattr(spec, "kv"):
            row["kv"] = str(spec.kv)
        if hasattr(spec, "zero_tension"):
            row["zero_tension"] = "1" if spec.zero_tension else "0"

        return row

    def collect_to_instances(self, instances: list):
        """Write table edits back to LayerInstance specs."""
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
        """Update a LayerInstance's spec from a table row dict."""
        spec = li.spec
        if spec is None:
            return

        def fval(key, default=0.0):
            try:
                return float(row.get(key, default))
            except (ValueError, TypeError):
                return default

        def ival(key, default=0):
            try:
                return int(float(row.get(key, default)))
            except (ValueError, TypeError):
                return default

        def bval(key, default=False):
            v = row.get(key, "0")
            return str(v) == "1"

        if hasattr(spec, "thickness"):
            spec.thickness = fval("thickness", spec.thickness)
        if hasattr(spec, "toc"):
            spec.toc = fval("toc", spec.toc)
        if hasattr(spec, "recess_depth"):
            spec.recess_depth = fval("recess_depth", spec.recess_depth)
        if hasattr(spec, "slab_thickness"):
            spec.slab_thickness = fval("slab_thickness", spec.slab_thickness)
        if hasattr(spec, "priority"):
            spec.priority = ival("priority", spec.priority)
        if hasattr(spec, "axis"):
            spec.axis = fval("axis", getattr(spec, "axis", 0))
        if hasattr(spec, "mesh_as_slab"):
            spec.mesh_as_slab = bval("mesh_as_slab")
        if hasattr(spec, "width"):
            spec.width = fval("width", spec.width)
        if hasattr(spec, "depth"):
            spec.depth = fval("depth", spec.depth)
        if hasattr(spec, "height"):
            spec.height = fval("height", spec.height)
        if hasattr(spec, "stiffness_factor"):
            spec.stiffness_factor = fval("stiffness_factor", 1.0)
        if hasattr(spec, "fixed_near"):
            spec.fixed_near = bval("fixed_near")
        if hasattr(spec, "fixed_far"):
            spec.fixed_far = bval("fixed_far")
        if hasattr(spec, "roller"):
            spec.roller = bval("roller")
        if hasattr(spec, "below_slab"):
            spec.below_slab = bval("below_slab")
        if hasattr(spec, "above_slab"):
            spec.above_slab = bval("above_slab")
        if hasattr(spec, "compressible"):
            spec.compressible = bval("compressible")
        if hasattr(spec, "shear_wall"):
            spec.shear_wall = bval("shear_wall")
        if hasattr(spec, "use_specified_LLR"):
            spec.specified_LLR = fval("specified_LLR", 0)
        if hasattr(spec, "spring_kv"):
            spec.spring_kv = fval("spring_kv", 0)
        if hasattr(spec, "kv"):
            spec.kv = fval("kv", 40000)
        if hasattr(spec, "zero_tension"):
            spec.zero_tension = bval("zero_tension")

    def _on_cell_change(self, role, item_id, col_key, new_value):
        """Callback when a cell value changes — sync back to app config."""
        # We sync lazily — the app reads tables before running import
        pass
