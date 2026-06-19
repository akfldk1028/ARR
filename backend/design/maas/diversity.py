"""Diversity scoring for MAAS mass variants."""

from __future__ import annotations

from shapely.geometry import Polygon


def polygon_iou(a: Polygon, b: Polygon) -> float:
    """Return footprint IoU in [0, 1]."""
    if a is None or b is None or a.is_empty or b.is_empty:
        return 0.0
    union_area = a.union(b).area
    if union_area <= 0:
        return 0.0
    return float(a.intersection(b).area / union_area)


def shape_signature(polygon: Polygon) -> dict[str, float]:
    """Compact footprint descriptors used for ranking and UI explanation."""
    if polygon is None or polygon.is_empty or polygon.area <= 0:
        return {"area": 0.0, "perimeter": 0.0, "compactness": 9999.0}
    return {
        "area": round(float(polygon.area), 3),
        "perimeter": round(float(polygon.length), 3),
        "compactness": round(float((polygon.length ** 2) / polygon.area), 3),
    }


def diversity_score(candidate: Polygon, previous: list[Polygon], source: Polygon | None = None) -> float:
    """Prefer variants that differ from the source and from already selected variants."""
    comparisons = [p for p in previous if p is not None and not p.is_empty]
    if source is not None and not source.is_empty:
        comparisons.append(source)
    if not comparisons:
        return 1.0
    max_iou = max(polygon_iou(candidate, other) for other in comparisons)
    return round(max(0.0, 1.0 - max_iou), 4)


__all__ = ["diversity_score", "polygon_iou", "shape_signature"]
