"""
theme.py
========
Colour palette and ttk styling for the DXF → RAM Concept GUI.
Dark professional theme matching structural engineering software aesthetics.
"""

from __future__ import annotations

# ── Colour Palette ────────────────────────────────────────────────────────────

C_BG = "#111827"  # main background
C_PANEL = "#182235"  # panel/frame background
C_SURFACE = "#202B3F"  # raised panels
C_ACCENT = "#2563EB"  # primary accent
C_ACCENT2 = "#14B8A6"  # secondary accent
C_TEXT = "#E5E7EB"  # primary text
C_MUTED = "#9CA3AF"  # muted/secondary text
C_SUCCESS = "#22C55E"  # success green
C_WARN = "#F59E0B"  # warning amber
C_TIP = "#FBBF24"  # tip / instruction text
C_ERROR = "#EF4444"  # error red
C_ENTRY_BG = "#0F172A"  # entry field background
C_BORDER = "#334155"  # borders and separators
C_TABLE_BG = "#101827"  # table background
C_TABLE_SEL = "#1D4ED8"  # table row selection
C_TABLE_HDR = "#1E293B"  # table header background
C_HEADER_FG = "#BAE6FD"  # table header text


def configure_ttk_style(style):
    """Configure ttk styles for the dark theme."""
    style.theme_use("default")

    # Notebook
    style.configure("Dark.TNotebook", background=C_BG, borderwidth=0, tabmargins=[8, 0, 8, 0])
    style.configure(
        "Dark.TNotebook.Tab",
        background=C_PANEL,
        foreground=C_MUTED,
        padding=[16, 8],
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Dark.TNotebook.Tab",
        background=[("selected", C_SURFACE), ("active", C_BORDER)],
        foreground=[("selected", C_TEXT), ("active", C_TEXT)],
    )

    # Inner notebook (for sub-tabs within structure/loads)
    style.configure("Inner.TNotebook", background=C_PANEL, borderwidth=0)
    style.configure(
        "Inner.TNotebook.Tab",
        background=C_BORDER,
        foreground=C_MUTED,
        padding=[12, 5],
        font=("Segoe UI", 8, "bold"),
    )
    style.map(
        "Inner.TNotebook.Tab",
        background=[("selected", C_ACCENT2), ("active", C_BORDER)],
        foreground=[("selected", "#042F2E"), ("active", C_TEXT)],
    )

    # Combobox
    style.configure(
        "Dark.TCombobox",
        fieldbackground=C_ENTRY_BG,
        background=C_BORDER,
        foreground=C_TEXT,
        arrowcolor=C_TEXT,
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", C_ENTRY_BG)],
        foreground=[("readonly", C_TEXT)],
    )

    # Scrollbar
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=C_BORDER,
        troughcolor=C_PANEL,
        arrowcolor=C_TEXT,
    )

    # Treeview (for editable tables)
    style.configure(
        "Dark.Treeview",
        background=C_TABLE_BG,
        foreground=C_TEXT,
        fieldbackground=C_TABLE_BG,
        rowheight=28,
        font=("Segoe UI", 9),
    )
    style.configure(
        "Dark.Treeview.Heading",
        background=C_TABLE_HDR,
        foreground=C_HEADER_FG,
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", C_TABLE_SEL)],
        foreground=[("selected", C_TEXT)],
    )
