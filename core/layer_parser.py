"""
layer_parser.py
===============
Keyword-based auto-detection of structural element layers from DXF files.

Scans all layer names in a DXF file and matches them against known element
keywords (e.g. layer containing 'column' → column role). Supports multiple
layers per element type, each with independently configurable properties.

Also extracts dimension hints from layer names where possible
(e.g. 'GC-BEAMS 25x80' → width=25, depth=80 in DXF units).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.constants import ELEMENT_KEYWORDS, ALL_ROLES
from core.geometry import parse_dimensions_from_layer_name, DimensionHint
from core.models import (
    LayerInstance,
    SPEC_FACTORY,
    SlabSpec,
    BeamSpec,
    ColumnSpec,
    WallSpec,
)


@dataclass
class ParsedLayer:
    """Result of parsing a single DXF layer name."""

    layer_name: str
    role: Optional[str] = None  # matched element role or None
    keyword_matched: str = ""  # the keyword that matched
    dimension_hint: Optional[DimensionHint] = None
    is_matched: bool = False


def detect_role(layer_name: str) -> Optional[tuple[str, str]]:
    """Detect the element role from a layer name.

    Returns (role, matched_keyword) or None if no match.
    Checks keywords longest-first to avoid partial matches
    (e.g. 'lineload' before 'line').
    """
    name_lower = layer_name.lower()

    # Sort roles by keyword length descending to match longest first
    candidates: list[tuple[str, str]] = []
    for role, keywords in ELEMENT_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                candidates.append((role, kw))

    if not candidates:
        return None

    # Pick the longest keyword match (most specific)
    candidates.sort(key=lambda c: len(c[1]), reverse=True)
    return candidates[0]


def parse_all_layers(layer_names: list[str]) -> list[ParsedLayer]:
    """Parse all DXF layer names and detect element roles.

    Returns a list of ParsedLayer objects, one per input layer name.
    Matched layers have role != None; unmatched layers have role == None.
    """
    results = []
    for name in sorted(layer_names):
        match = detect_role(name)
        dim_hint = parse_dimensions_from_layer_name(name)
        if match:
            role, keyword = match
            results.append(
                ParsedLayer(
                    layer_name=name,
                    role=role,
                    keyword_matched=keyword,
                    dimension_hint=dim_hint,
                    is_matched=True,
                )
            )
        else:
            results.append(
                ParsedLayer(
                    layer_name=name,
                    role=None,
                    dimension_hint=dim_hint,
                    is_matched=False,
                )
            )
    return results


def create_layer_instances(
    parsed_layers: list[ParsedLayer],
    unit_scale: float = 1.0,
) -> list[LayerInstance]:
    """Create LayerInstance objects from parsed layers.

    For each matched layer, creates a LayerInstance with default spec values,
    then applies any dimension hints found in the layer name.

    Args:
        parsed_layers: Output of parse_all_layers()
        unit_scale: Conversion factor from DXF units to metres
    """
    instances = []
    for pl in parsed_layers:
        if not pl.is_matched or pl.role is None:
            continue

        li = LayerInstance(
            layer_name=pl.layer_name,
            role=pl.role,
            enabled=True,
        )

        # Apply dimension hints from layer name
        hint = pl.dimension_hint
        if hint and li.spec is not None:
            _apply_dimension_hint(li, hint, unit_scale)

        instances.append(li)

    return instances


def _apply_dimension_hint(
    li: LayerInstance,
    hint: DimensionHint,
    unit_scale: float,
) -> None:
    """Apply parsed dimension hints to a LayerInstance's spec.

    Interprets dimensions based on the element role:
    - Beam '25x80' → width=25*scale, depth=80*scale
    - Slab '300' → thickness=300*scale
    - Column '400x600' → b=400*scale, d=600*scale
    """
    spec = li.spec
    if spec is None:
        return

    if isinstance(spec, BeamSpec) and hint.has_two_dims:
        spec.width = hint.dim1 * unit_scale
        spec.depth = hint.dim2 * unit_scale

    elif isinstance(spec, SlabSpec) and hint.has_one_dim:
        spec.thickness = hint.dim1 * unit_scale

    elif isinstance(spec, ColumnSpec) and hint.has_two_dims:
        spec.b = hint.dim1 * unit_scale
        spec.d = hint.dim2 * unit_scale

    elif isinstance(spec, WallSpec) and hint.has_one_dim:
        spec.thickness = hint.dim1 * unit_scale
