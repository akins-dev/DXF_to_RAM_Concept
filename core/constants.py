"""
constants.py
============
Design codes, structure types, unit scales, and element keywords
for the DXF → RAM Concept importer.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Design code & structure type registries
#
# At runtime, these are populated from the actual RAM Concept API via
# core.api_discovery. The hardcoded values below are only used as a
# FALLBACK when the API is not importable (e.g. for preview-only mode
# or running on a machine without RAM Concept installed).
# ---------------------------------------------------------------------------

# Fallback values — used only when RAM Concept API is not available
_FALLBACK_DESIGN_CODES: dict[str, str] = {
    "ACI 318-14 (SI)":   "ACI318_14_SI",
    "ACI 318-19 (SI)":   "ACI318_19_SI",
    "ACI 318-14 (US)":   "ACI318_14_US",
    "ACI 318-19 (US)":   "ACI318_19_US",
    "AS 3600-2009":      "AS3600_2009",
    "AS 3600-2018":      "AS3600_2018",
    "Eurocode 2-2004":   "EC2_2004",
    "BS 8110:1997":      "BS8110_1997",
    "CAN/CSA A23.3-04":  "CSA_A23_3_04",
    "IS 456:2000":       "IS456_2000",
}

_FALLBACK_STRUCTURE_TYPES: dict[str, str] = {
    "Elevated slab": "ELEVATED",
    "Mat / Raft foundation": "MAT",
}

# These are the active registries — updated by load_api_enums()
DESIGN_CODES: dict[str, str] = dict(_FALLBACK_DESIGN_CODES)
STRUCTURE_TYPES: dict[str, str] = dict(_FALLBACK_STRUCTURE_TYPES)


def load_api_enums(api_path: str = "") -> bool:
    """Discover enum values from the actual RAM Concept API.
    
    Replaces the fallback values in DESIGN_CODES and STRUCTURE_TYPES
    with the real API enum members. Returns True if discovery succeeded.
    """
    from core.api_discovery import get_design_codes, get_structure_types, reset_cache

    reset_cache()
    codes = get_design_codes(api_path)
    types = get_structure_types(api_path)

    if codes:
        DESIGN_CODES.clear()
        DESIGN_CODES.update(codes)
    if types:
        STRUCTURE_TYPES.clear()
        STRUCTURE_TYPES.update(types)

    return bool(codes or types)

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
    "recess": ["recess", "stepdown", "step_down", "step down", "depression"],
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
    "recess",
    "point_support",
    "line_support",
    "area_spring",
]

LOAD_ROLES = ["lineload", "areaload", "pointload"]

ALL_ROLES = STRUCTURAL_ROLES + LOAD_ROLES

# ---------------------------------------------------------------------------
# Live load type options
# ---------------------------------------------------------------------------

LIVE_LOAD_TYPES = ["Reducible", "Unreducible"]
