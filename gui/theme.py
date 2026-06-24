"""
theme.py
========
Colour palette and ttk styling for the DXF → RAM Concept GUI.
Dark professional theme matching structural engineering software aesthetics.
"""

from __future__ import annotations

# ── Colour Palette ────────────────────────────────────────────────────────────

C_BG = "#1C2333"  # main background
C_PANEL = "#232D42"  # panel/frame background
C_ACCENT = "#3B82F6"  # primary accent (blue)
C_ACCENT2 = "#22D3EE"  # secondary accent (cyan)
C_TEXT = "#E2E8F0"  # primary text
C_MUTED = "#94A3B8"  # muted/secondary text
C_SUCCESS = "#4ADE80"  # success green
C_WARN = "#FACC15"  # warning yellow
C_ERROR = "#F87171"  # error red
C_ENTRY_BG = "#2D3A52"  # entry field background
C_BORDER = "#3B4A6A"  # borders and separators
C_TABLE_BG = "#1E293B"  # table background
C_TABLE_SEL = "#334155"  # table row selection
C_TABLE_HDR = "#2D3A52"  # table header background
C_HEADER_FG = "#38BDF8"  # table header text


def configure_ttk_style(style):
    """Configure ttk styles for the dark theme."""
    style.theme_use("default")

    # Notebook
    style.configure("Dark.TNotebook", background=C_BG, borderwidth=0)
    style.configure(
        "Dark.TNotebook.Tab",
        background=C_PANEL,
        foreground=C_MUTED,
        padding=[14, 6],
        font=("Segoe UI", 9),
    )
    style.map(
        "Dark.TNotebook.Tab",
        background=[("selected", C_ACCENT)],
        foreground=[("selected", "#FFFFFF")],
    )

    # Inner notebook (for sub-tabs within structure/loads)
    style.configure("Inner.TNotebook", background=C_PANEL, borderwidth=0)
    style.configure(
        "Inner.TNotebook.Tab",
        background=C_BORDER,
        foreground=C_MUTED,
        padding=[10, 4],
        font=("Segoe UI", 8),
    )
    style.map(
        "Inner.TNotebook.Tab",
        background=[("selected", C_ACCENT2)],
        foreground=[("selected", "#0F172A")],
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
        rowheight=26,
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
