"""
api_discovery.py
================
Runtime discovery of RAM Concept API enum values.

Instead of hardcoding DesignCode and StructureType enum names,
this module introspects the actual API classes at runtime and
provides mappings.

Usage:
    from core.api_discovery import get_design_codes, get_structure_types

    # Returns dict like {"ACI 318-14": "ACI318_14", ...}
    codes = get_design_codes(api_path="/path/to/python")
"""

from __future__ import annotations

import sys
import re
from typing import Optional


# ── Cache ─────────────────────────────────────────────────────────────────────

_cached_design_codes: Optional[dict[str, str]] = None
_cached_structure_types: Optional[dict[str, str]] = None


def _ensure_api_on_path(api_path: str):
    """Add the RAM Concept Python API to sys.path if not already present."""
    if api_path and api_path not in sys.path:
        sys.path.insert(1, api_path)


def _enum_members(cls) -> list[str]:
    """Extract public uppercase member names from a class/enum.
    
    Handles both Python Enum subclasses and plain classes with class attributes.
    """
    members = []
    for name in dir(cls):
        if name.startswith("_"):
            continue
        # Skip methods and builtins
        val = getattr(cls, name, None)
        if callable(val) and not isinstance(val, cls):
            continue
        # Keep only UPPER/MixedCase names (enum-like)
        if name[0].isupper() or name[0].isdigit():
            members.append(name)
    return sorted(members)


def _humanize_design_code(enum_name: str) -> str:
    """Convert an API enum name to a human-readable label.
    
    Examples:
        ACI318_14       → ACI 318-14
        ACI318_14_SI    → ACI 318-14 (SI)
        ACI318_14_US    → ACI 318-14 (US)
        BS8110_1997     → BS 8110:1997
        AS3600_2009     → AS 3600-2009
        AS3600_2018     → AS 3600-2018
        EC2_2004        → Eurocode 2-2004
        CSA_A23_3_04    → CAN/CSA A23.3-04
        IS456_2000      → IS 456:2000
    """
    name = enum_name

    # Detect SI/US suffix
    suffix = ""
    if name.endswith("_SI"):
        suffix = " (SI)"
        name = name[:-3]
    elif name.endswith("_US"):
        suffix = " (US)"
        name = name[:-3]

    # Special cases
    if name.startswith("EC2"):
        year = name.replace("EC2_", "").replace("EC2", "")
        return f"Eurocode 2-{year}{suffix}" if year else f"Eurocode 2{suffix}"

    if name.startswith("CSA"):
        # CSA_A23_3_04 → CAN/CSA A23.3-04
        parts = name.replace("CSA_", "").split("_")
        if len(parts) >= 3 and parts[0] == "A23":
            return f"CAN/CSA A23.{parts[1]}-{parts[2]}{suffix}"
        return f"CAN/CSA {name.replace('CSA_', '')}{suffix}"

    # Generic: split code from year
    # ACI318_14 → ACI 318-14
    # BS8110_1997 → BS 8110:1997
    # AS3600_2009 → AS 3600-2009
    # IS456_2000 → IS 456:2000
    match = re.match(r"^([A-Z]+)(\d+)(?:_(\d+))?$", name)
    if match:
        prefix = match.group(1)   # ACI, BS, AS, IS
        code_num = match.group(2) # 318, 8110, 3600, 456
        year = match.group(3)     # 14, 1997, 2009, 2000

        # Separator: BS and IS use ':', others use '-'
        sep = ":" if prefix in ("BS", "IS") else "-"

        if year:
            return f"{prefix} {code_num}{sep}{year}{suffix}"
        return f"{prefix} {code_num}{suffix}"

    # Fallback: return as-is
    return f"{enum_name}"


def _humanize_structure_type(enum_name: str) -> str:
    """Convert a StructureType enum name to a human-readable label.
    
    Examples:
        ELEVATED → Elevated slab
        MAT → Mat / Raft foundation
    """
    mapping = {
        "ELEVATED": "Elevated slab",
        "MAT": "Mat / Raft foundation",
        "POST_TENSIONED": "Post-tensioned slab",
        "MILD_REINFORCED": "Mild reinforced slab",
    }
    upper = enum_name.upper()
    if upper in mapping:
        return mapping[upper]
    # Fallback: capitalize and replace underscores
    return enum_name.replace("_", " ").capitalize()


# ── Public API ────────────────────────────────────────────────────────────────


def get_design_codes(api_path: str = "") -> dict[str, str]:
    """Discover DesignCode enum members from the RAM Concept API.
    
    Returns:
        dict mapping human-readable label → API enum member name
        e.g. {"ACI 318-14 (SI)": "ACI318_14_SI", ...}
    
    Falls back to an empty dict if the API is not available.
    """
    global _cached_design_codes
    if _cached_design_codes is not None:
        return _cached_design_codes

    _ensure_api_on_path(api_path)

    try:
        from ram_concept.model import DesignCode
        members = _enum_members(DesignCode)
        _cached_design_codes = {
            _humanize_design_code(m): m for m in members
        }
    except ImportError:
        _cached_design_codes = {}

    return _cached_design_codes


def get_structure_types(api_path: str = "") -> dict[str, str]:
    """Discover StructureType enum members from the RAM Concept API.
    
    Returns:
        dict mapping human-readable label → API enum member name
        e.g. {"Elevated slab": "ELEVATED", ...}
    
    Falls back to an empty dict if the API is not available.
    """
    global _cached_structure_types
    if _cached_structure_types is not None:
        return _cached_structure_types

    _ensure_api_on_path(api_path)

    try:
        from ram_concept.model import StructureType
        members = _enum_members(StructureType)
        _cached_structure_types = {
            _humanize_structure_type(m): m for m in members
        }
    except ImportError:
        _cached_structure_types = {}

    return _cached_structure_types


def reset_cache():
    """Clear cached discoveries (e.g. when API path changes)."""
    global _cached_design_codes, _cached_structure_types
    _cached_design_codes = None
    _cached_structure_types = None
