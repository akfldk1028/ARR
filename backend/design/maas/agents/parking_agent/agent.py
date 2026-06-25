"""Parking review agent for MAAS legal design."""

from __future__ import annotations

from design.maas.agents.shared.evidence import (
    feature_properties,
    parking_layout_candidate,
    parking_precheck,
    parking_required_spaces,
)
from design.maas.agents.shared.types import AgentCard, AgentContext, AgentResult


class ParkingAgent:
    agent_id = "parking_agent"
    display_name = "Parking Agent"
    role = "Summarize parking count/layout precheck evidence for the selected candidate."

    def run(self, context: AgentContext) -> AgentResult:
        props = feature_properties(context.feature)
        precheck = parking_precheck(props)
        layout = parking_layout_candidate(precheck)
        required = parking_required_spaces(precheck, layout)
        provided = layout.get("provided_spaces")
        status = layout.get("status") or "not_available"
        unmet = layout.get("unmet_spaces")
        has_layout = bool(layout)
        review_status = "pass" if status == "pass" else "check" if has_layout else "needs_evidence"

        return AgentResult(
            agent=self.agent_id,
            status=review_status,
            summary=f"parking layout status={status}; provided={provided}; required={required}",
            metrics={
                "layout_status": status,
                "required_spaces": required,
                "provided_spaces": provided,
                "unmet_spaces": unmet,
            },
            role=self.role,
            next_agent="maas_geometry_agent",
        )

    def build_card(self) -> dict[str, Any]:
        return AgentCard(
            name=self.agent_id,
            display_name=self.display_name,
            description=self.role,
            skills=["parking_count_review", "layout_candidate_review"],
            endpoint="/design/maas/agents/parking_agent",
        ).to_dict()


__all__ = ["ParkingAgent"]
