"""Canonical MAAS law-to-design agent flow."""

from __future__ import annotations


REVIEW_AGENT_SEQUENCE = (
    "law_graph_agent",
    "parking_agent",
    "maas_geometry_agent",
    "review_agent",
)

FLOW_AGENT_SEQUENCE = (
    "design_orchestrator",
    *REVIEW_AGENT_SEQUENCE,
)

FLOW_STEPS = [
    ("user", "design_orchestrator", "PNU/design 후보를 받으면 법규-주차-매스-검토 순서로 협업을 시작해."),
    ("design_orchestrator", "law_graph_agent", "Graph DB 법규 근거와 누락 evidence를 rule_id 중심으로 확인해."),
    ("law_graph_agent", "parking_agent", "법규 검토 결과를 받아 주차 산정 대수와 연접/차로 조건을 검토해."),
    ("parking_agent", "maas_geometry_agent", "주차 조건을 반영해 가능한 MAAS 매스 repair operation을 제안해."),
    ("maas_geometry_agent", "review_agent", "법규/주차/매스 evidence를 묶어 통과/보류/실패 리스크를 판정해."),
    ("review_agent", "design_orchestrator", "최종 판단과 다음 수정 지시를 사용자에게 전달할 형태로 정리해."),
]


def build_flow_edges() -> list[dict[str, str]]:
    return [
        {"source": source, "target": target, "label": message}
        for source, target, message in FLOW_STEPS
    ]


__all__ = ["FLOW_AGENT_SEQUENCE", "FLOW_STEPS", "REVIEW_AGENT_SEQUENCE", "build_flow_edges"]
