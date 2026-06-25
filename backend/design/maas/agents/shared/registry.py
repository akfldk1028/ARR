"""Registry for deterministic ARR MAAS design agents."""

from __future__ import annotations

from typing import Any

from design.maas.agents.orchestrator.agent import DesignOrchestratorAgent
from design.maas.agents.orchestrator.flow import FLOW_AGENT_SEQUENCE, REVIEW_AGENT_SEQUENCE
from design.maas.agents.law_graph_agent.agent import LawGraphAgent
from design.maas.agents.maas_geometry_agent.agent import MaasGeometryAgent
from design.maas.agents.parking_agent.agent import ParkingAgent
from design.maas.agents.review_agent.agent import ReviewAgent
from design.maas.agents.shared.types import AgentContext, MaasAgent


AGENT_SEQUENCE = REVIEW_AGENT_SEQUENCE


def build_agent_registry() -> dict[str, MaasAgent]:
    agents: list[MaasAgent] = [
        DesignOrchestratorAgent(),
        LawGraphAgent(),
        ParkingAgent(),
        MaasGeometryAgent(),
        ReviewAgent(),
    ]
    return {agent.agent_id: agent for agent in agents}


def build_agent_cards() -> list[dict[str, Any]]:
    registry = build_agent_registry()
    return [registry[agent_id].build_card() for agent_id in FLOW_AGENT_SEQUENCE]


def run_review_flow(context: AgentContext) -> list[dict[str, Any]]:
    registry = build_agent_registry()
    return [registry[agent_id].run(context).to_review() for agent_id in AGENT_SEQUENCE]


__all__ = ["AGENT_SEQUENCE", "build_agent_cards", "build_agent_registry", "run_review_flow"]
