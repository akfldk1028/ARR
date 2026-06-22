"""
Land regulation registry — modular spec of all 법규 regulation lines.

Each regulation type is a discrete unit with:
- 고유 키 (프런트/CLI/Neo4j 공통 식별자)
- 법근거 (건축법/시행령/지구단위계획 조문)
- 적용 조건 (용도지역, 규제 플래그)
- 선 종류 (2D polygon / 2D line / 3D envelope / overlay-only)

To add a new regulation: append a RegulationSpec to REGISTRY and (if
geometry is computed) wire it in setback_geometry.compute_setback_lines.
"""

from .registry import (
    LineType,
    RegulationSpec,
    REGISTRY,
    applicable_for,
    find,
)
from .building_context import (
    BuildingContext,
    RoadSegment,
    effective_height,
    weighted_road_level,
    sunlight_setback_for_height,
    sunlight_rules_for_context,
    daylight_distance,
    daylight_multiplier_for_zone,
    summarize,
    SUNLIGHT_LOW_THRESHOLD_M,
    SUNLIGHT_LOW_SETBACK_M,
    SUNLIGHT_HIGH_MULTIPLIER,
)

__all__ = [
    "LineType", "RegulationSpec", "REGISTRY", "applicable_for", "find",
    "BuildingContext", "effective_height",
    "sunlight_setback_for_height", "sunlight_rules_for_context",
    "daylight_distance", "daylight_multiplier_for_zone", "summarize",
    "SUNLIGHT_LOW_THRESHOLD_M", "SUNLIGHT_LOW_SETBACK_M",
    "SUNLIGHT_HIGH_MULTIPLIER",
]
