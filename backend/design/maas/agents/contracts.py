"""Agent review contracts for conversational MAAS editing."""

from __future__ import annotations

from typing import Any


def _metric(props: dict[str, Any], key: str) -> float | None:
    value = props.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def build_agent_reviews(
    *,
    operation_type: str,
    feature: dict[str, Any],
    constraints: dict[str, Any] | None,
    rejected: list[dict[str, Any]] | None = None,
    geometry_notes: list[str] | None = None,
) -> list[dict[str, Any]]:
    props = feature.get("properties") or {}
    constraints = constraints or {}
    rejected = rejected or []
    geometry_notes = geometry_notes or []
    far = _metric(props, "far")
    bcr = _metric(props, "bcr")
    height = _metric(props, "height")
    far_limit = _metric(constraints, "far_limit")
    bcr_limit = _metric(constraints, "bcr_limit")
    height_limit = _metric(constraints, "height_limit")

    legal_pass = True
    if far is not None and far_limit is not None and far > far_limit + 0.1:
        legal_pass = False
    if bcr is not None and bcr_limit is not None and bcr > bcr_limit + 0.1:
        legal_pass = False
    if height is not None and height_limit is not None and height > height_limit + 0.1:
        legal_pass = False

    far_util = min(1.0, far / far_limit) if far is not None and far_limit and far_limit > 0 else None
    bcr_util = min(1.0, bcr / bcr_limit) if bcr is not None and bcr_limit and bcr_limit > 0 else None

    return [
        {
            "agent": "geometry_agent",
            "status": "done",
            "summary": "; ".join(geometry_notes) if geometry_notes else f"operation {operation_type} normalized into a MAAS seed",
        },
        {
            "agent": "law_agent",
            "status": "pass" if legal_pass else "fail",
            "summary": "FAR/BCR/height metrics are within returned legal limits" if legal_pass else "Returned mass exceeds at least one legal metric",
            "metrics": {"far": far, "bcr": bcr, "height": height, "far_limit": far_limit, "bcr_limit": bcr_limit, "height_limit": height_limit},
        },
        {
            "agent": "optimization_agent",
            "status": "done",
            "summary": "Candidate ranked by legal FAR/BCR utilization plus diversity",
            "metrics": {"far_utilization": far_util, "bcr_utilization": bcr_util, "maas_score": props.get("maas_score")},
        },
        {
            "agent": "review_agent",
            "status": "done",
            "summary": f"{len(rejected)} rejected candidates kept for audit; selected mass_shape={props.get('mass_shape')}",
        },
    ]


__all__ = ["build_agent_reviews"]
