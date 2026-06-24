"""
constants.py
============
Design codes, structure types, unit scales, and element keywords
for the DXF → RAM Concept importer.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Design code registry — human label → RAM Concept API enum member name
# ---------------------------------------------------------------------------

DESIGN_CODES: dict[str, str] = {
    "ACI 318-14 (SI)": "ACI318_14SI",
    "ACI 318-19 (SI)": "ACI318_19SI",
    "ACI 318-99 (US)": "ACI318_99US",
    "AS 3600-2009": "AS3600_09",
    "AS 3600-2018": "AS3600_18",
    "Eurocode 2-2004": "EC2_04SI",
    "BS 8110:1997": "BS8110_97SI",
    "CAN/CSA A23.3-04": "CSA_A23_04SI",
    "IS 456:2000": "IS456_00SI",
}

STRUCTURE_TYPES: dict[str, str] = {
    "Elevated slab": "ELEVATED",
    "Mat / Raft foundation": "MAT",
}

# ---------------------------------------------------------------------------
# Unit scales — DXF drawing units → conversion factor to metres
# ---------------------------------------------------------------------------

UNIT_SCALES: dict[str, float] = {
    "Millimetres (mm)": 0.001,
    "Centimetres (cm)": 0.01,
    "Metres (m)": 1.0,
    "Inches (in)": 0.0254,
    "Feet (ft)": 0.3048,
    "Custom…": 1.0,
}

# ---------------------------------------------------------------------------
# Element type keywords — used for auto-detecting layers from DXF
# The key is the canonical element role; the value is a list of
# substrings to search for (case-insensitive) in DXF layer names.
# ---------------------------------------------------------------------------

ELEMENT_KEYWORDS: dict[str, list[str]] = {
    "slab": ["slab"],
    "beam": ["beam"],
    "column": ["column", "col"],
    "wall": ["wall"],
    "opening": ["opening", "void"],
    "drop_cap": ["drop_cap", "dropcap", "drop cap"],
    "drop_panel": ["drop_panel", "droppanel", "drop panel"],
    "point_support": ["point_support", "pointsupport"],
    "line_support": ["line_support", "linesupport"],
    "area_spring": ["area_spring", "areaspring"],
    "lineload": ["lineload", "line_load", "line load"],
    "areaload": ["areaload", "area_load", "area load"],
    "pointload": ["pointload", "point_load", "point load"],
}

# Canonical ordering for GUI tabs
STRUCTURAL_ROLES = [
    "slab",
    "beam",
    "column",
    "wall",
    "opening",
    "drop_cap",
    "drop_panel",
    "point_support",
    "line_support",
    "area_spring",
]

LOAD_ROLES = ["lineload", "areaload", "pointload"]

ALL_ROLES = STRUCTURAL_ROLES + LOAD_ROLES

# ---------------------------------------------------------------------------
# Live load type options
# ---------------------------------------------------------------------------

LIVE_LOAD_TYPES = ["Unreducible", "Reducible"]
