"""
widgets.py
==========
Reusable styled Tkinter widgets for the DXF → RAM Concept GUI.
Includes entries, checkboxes, buttons, section labels, and
an editable Treeview table widget.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from gui.theme import *

# ── Basic styled widgets ──────────────────────────────────────────────────────


def styled_entry(parent, textvariable, width=18, **kw):
    return tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg=C_ENTRY_BG,
        fg=C_TEXT,
        insertbackground=C_TEXT,
        relief="flat",
        bd=4,
        **kw,
    )


def styled_check(parent, text, variable, **kw):
    bg = parent.cget("bg")
    return tk.Checkbutton(
        parent,
        text=text,
        variable=variable,
        bg=bg,
        fg=C_TEXT,
        selectcolor=C_ENTRY_BG,
        activebackground=bg,
        activeforeground=C_TEXT,
        **kw,
    )


def styled_label(parent, text, fg=C_TEXT, **kw):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=fg, **kw)


def styled_btn(parent, text, command, accent=False, danger=False, **kw):
    bg = C_ERROR if danger else C_ACCENT if accent else C_BORDER
    active_bg = C_ACCENT2 if accent else C_SURFACE
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg="#FFFFFF" if accent or danger else C_TEXT,
        activebackground=active_bg,
        activeforeground="#FFFFFF" if accent or danger else C_TEXT,
        relief="flat",
        bd=0,
        padx=12,
        pady=7,
        cursor="hand2",
        font=("Segoe UI", 9, "bold" if accent else "normal"),
        **kw,
    )


def section_label(parent, text):
    bg = parent.cget("bg")
    f = tk.Frame(parent, bg=bg)
    tk.Label(f, text=text, bg=bg, fg=C_ACCENT2, font=("Segoe UI", 9, "bold")).pack(
        side="left"
    )
    tk.Frame(f, bg=C_BORDER, height=1).pack(
        side="left", fill="x", expand=True, padx=(8, 0)
    )
    return f


def panel(parent, **kw):
    return tk.Frame(parent, bg=C_SURFACE, highlightbackground=C_BORDER, highlightthickness=1, **kw)


def panel_title(parent, title, subtitle=""):
    bg = parent.cget("bg")
    f = tk.Frame(parent, bg=bg)
    tk.Label(f, text=title, bg=bg, fg=C_TEXT, font=("Segoe UI", 11, "bold")).pack(
        anchor="w"
    )
    if subtitle:
        tk.Label(
            f,
            text=subtitle,
            bg=bg,
            fg=C_MUTED,
            font=("Segoe UI", 8),
            justify="left",
            wraplength=760,
        ).pack(anchor="w", pady=(2, 0))
    return f


def field_row(parent, row, label, widget, unit=""):
    bg = parent.cget("bg")
    tk.Label(parent, text=label, bg=bg, fg=C_MUTED, anchor="w").grid(
        row=row, column=0, sticky="w", padx=(0, 10), pady=5
    )
    widget.grid(row=row, column=1, sticky="we", pady=5)
    if unit:
        tk.Label(parent, text=unit, bg=bg, fg=C_MUTED).grid(
            row=row, column=2, sticky="w", padx=(8, 0), pady=5
        )
    parent.columnconfigure(1, weight=1)


def notice(parent, text, kind="info"):
    colors = {"info": C_ACCENT2, "warn": C_WARN, "error": C_ERROR, "success": C_SUCCESS}
    bg = parent.cget("bg")
    return tk.Label(
        parent,
        text=text,
        bg=bg,
        fg=colors.get(kind, C_ACCENT2),
        font=("Segoe UI", 8),
        justify="left",
        anchor="w",
        wraplength=820,
    )


# ── Editable Table Widget ────────────────────────────────────────────────────


class EditableTable(tk.Frame):
    """A Treeview-based table with inline editing support.

    Supports text entry and dropdown (combobox) editing for cells.
    Each column can be configured as editable or read-only, and can
    have a specific edit type ('entry', 'combo', 'check').
    """

    def __init__(self, parent, columns: list[dict], **kw):
        """
        Parameters
        ----------
        columns : list of dicts, each with keys:
            'key'      : internal column identifier
            'label'    : display header text
            'width'    : column width in pixels
            'editable' : bool (default True)
            'edit_type': 'entry' | 'combo' | 'check' (default 'entry')
            'values'   : list of values for combo type
            'anchor'   : 'w', 'center', 'e' (default 'center')
        """
        super().__init__(parent, bg=C_PANEL, **kw)
        self._columns = columns
        self._col_keys = [c["key"] for c in columns]
        self._on_change_cb: Optional[Callable] = None

        # Treeview
        self.tree = ttk.Treeview(
            self,
            columns=self._col_keys,
            show="headings",
            style="Dark.Treeview",
            selectmode="browse",
        )

        for col in columns:
            self.tree.heading(col["key"], text=col["label"])
            self.tree.column(
                col["key"],
                width=col.get("width", 100),
                anchor=col.get("anchor", "center"),
                minwidth=60,
            )

        # Scrollbar
        vsb = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.tree.yview,
            style="Dark.Vertical.TScrollbar",
        )
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Bind double-click for editing
        self.tree.bind("<Double-1>", self._on_double_click)

        # Current editor widget
        self._editor: Optional[tk.Widget] = None

    def set_on_change(self, callback: Callable):
        """Set callback for when a cell value changes.

        callback(item_id, column_key, new_value)
        """
        self._on_change_cb = callback

    def insert_row(self, values: dict, **kw) -> str:
        """Insert a row. values is a dict mapping column keys to values."""
        row_vals = [str(values.get(k, "")) for k in self._col_keys]
        return self.tree.insert("", "end", values=row_vals, **kw)

    def clear(self):
        """Remove all rows."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def get_all_data(self) -> list[dict]:
        """Return all rows as list of dicts."""
        data = []
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            row = {k: v for k, v in zip(self._col_keys, vals)}
            data.append(row)
        return data

    def get_row_data(self, item_id: str) -> dict:
        """Return one row as a dict."""
        vals = self.tree.item(item_id, "values")
        return {k: v for k, v in zip(self._col_keys, vals)}

    def set_cell(self, item_id: str, column_key: str, value: str):
        """Set a single cell value."""
        col_idx = self._col_keys.index(column_key)
        vals = list(self.tree.item(item_id, "values"))
        vals[col_idx] = str(value)
        self.tree.item(item_id, values=vals)

    def _on_double_click(self, event):
        """Handle double-click to start editing a cell."""
        self._destroy_editor()

        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or not column:
            return

        # column is like '#1', '#2', etc.
        col_idx = int(column.replace("#", "")) - 1
        if col_idx < 0 or col_idx >= len(self._columns):
            return

        col_def = self._columns[col_idx]
        if not col_def.get("editable", True):
            return

        # Get cell bounding box
        bbox = self.tree.bbox(item, column)
        if not bbox:
            return

        x, y, w, h = bbox
        current_value = self.tree.item(item, "values")[col_idx]

        edit_type = col_def.get("edit_type", "entry")

        if edit_type == "combo":
            self._create_combo_editor(
                item, col_idx, x, y, w, h, current_value, col_def.get("values", [])
            )
        elif edit_type == "check":
            # Toggle 0/1
            new_val = "0" if str(current_value) == "1" else "1"
            self._apply_edit(item, col_idx, new_val)
        else:
            self._create_entry_editor(item, col_idx, x, y, w, h, current_value)

    def _create_entry_editor(self, item, col_idx, x, y, w, h, value):
        var = tk.StringVar(value=str(value))
        editor = tk.Entry(
            self.tree,
            textvariable=var,
            bg=C_ENTRY_BG,
            fg=C_TEXT,
            insertbackground=C_TEXT,
            relief="flat",
            bd=2,
            font=("Segoe UI", 9),
        )
        editor.place(x=x, y=y, width=w, height=h)
        editor.select_range(0, "end")
        editor.focus_set()

        def commit(e=None):
            self._apply_edit(item, col_idx, var.get())
            self._destroy_editor()

        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", lambda e: self._destroy_editor())
        self._editor = editor

    def _create_combo_editor(self, item, col_idx, x, y, w, h, value, options):
        var = tk.StringVar(value=str(value))
        editor = ttk.Combobox(
            self.tree,
            textvariable=var,
            values=options,
            state="readonly",
            style="Dark.TCombobox",
            font=("Segoe UI", 9),
        )
        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_set()

        def commit(e=None):
            self._apply_edit(item, col_idx, var.get())
            self._destroy_editor()

        editor.bind("<<ComboboxSelected>>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", lambda e: self._destroy_editor())
        self._editor = editor

    def _apply_edit(self, item, col_idx, new_value):
        vals = list(self.tree.item(item, "values"))
        vals[col_idx] = str(new_value)
        self.tree.item(item, values=vals)
        if self._on_change_cb:
            col_key = self._col_keys[col_idx]
            self._on_change_cb(item, col_key, new_value)

    def _destroy_editor(self):
        if self._editor:
            try:
                self._editor.destroy()
            except Exception:
                pass
            self._editor = None
