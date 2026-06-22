"""
Zoning Mapper - maps zoning zone names to BCR/FAR limits.

Loads static data from data/zoning_limits.json.
When multiple zones apply, the strictest (lowest) limits are used per 국토계획법 제76-77조.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "zoning_limits.json"
_ZONES: dict[str, dict] = {}


def _load():
    global _ZONES
    if _ZONES:
        return
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _ZONES = {z["zone_name"]: z for z in data["zones"]}
        logger.info(f"Loaded {len(_ZONES)} zoning zones from {_DATA_PATH}")
    except Exception as e:
        logger.error(f"Failed to load zoning data: {e}")
        _ZONES = {}


def get_all_zones() -> list[dict]:
    """Return all zoning zone definitions."""
    _load()
    return list(_ZONES.values())


def lookup(zone_name: str) -> dict | None:
    """
    Look up a single zone by exact name. Returns None if not found.

    Only exact matches are accepted to avoid ambiguity
    (e.g. "일반주거" could match 제1종/제2종/제3종 with different limits).
    """
    _load()
    return _ZONES.get(zone_name)


def resolve_limits(zone_names: list[str]) -> dict:
    """
    Given a list of zone names, compute the effective BCR/FAR limits.

    When multiple zones apply, use the strictest (lowest) value.

    Returns:
        {
            "bcr_limit": float,
            "far_limit": float,
            "zones": [{"zone_name": ..., "bcr_default": ..., "far_default": ..., ...}],
            "matched": int,
            "unmatched": [str]
        }
    """
    _load()
    matched_zones = []
    unmatched = []

    for name in zone_names:
        zone = lookup(name)
        if zone:
            matched_zones.append(zone)
        else:
            unmatched.append(name)

    if not matched_zones:
        return {
            "bcr_limit": None,
            "far_limit": None,
            "zones": [],
            "matched": 0,
            "unmatched": unmatched,
        }

    bcr_limit = min(z["bcr_default"] for z in matched_zones)
    far_limit = min(z["far_default"] for z in matched_zones)

    return {
        "bcr_limit": bcr_limit,
        "far_limit": far_limit,
        "zones": matched_zones,
        "matched": len(matched_zones),
        "unmatched": unmatched,
    }
