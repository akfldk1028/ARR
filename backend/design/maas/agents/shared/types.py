"""Shared contracts for MAAS design agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentContext:
    operation_type: str
    feature: dict[str, Any]
    constraints: dict[str, Any]
    rejected: list[dict[str, Any]] = field(default_factory=list)
    geometry_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentResult:
    agent: str
    status: str
    summary: str
    metrics: dict[str, Any] | None = None
    role: str | None = None
    next_agent: str | None = None

    def to_review(self) -> dict[str, Any]:
        review: dict[str, Any] = {
            "agent": self.agent,
            "status": self.status,
            "summary": self.summary,
        }
        if self.metrics is not None:
            review["metrics"] = self.metrics
        if self.role:
            review["role"] = self.role
        if self.next_agent:
            review["next_agent"] = self.next_agent
        return review


@dataclass(frozen=True)
class AgentCard:
    name: str
    display_name: str
    description: str
    skills: list[str]
    endpoint: str
    input_schema: str = "arr.maas.agent_context.v0"
    output_schema: str = "arr.maas.agent_review.v0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": {
                "streaming": False,
                "deterministic": True,
            },
            "skills": [
                {"id": skill, "name": skill.replace("_", " ").title()}
                for skill in self.skills
            ],
            "endpoint": self.endpoint,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class MaasAgent(Protocol):
    agent_id: str
    display_name: str
    role: str

    def run(self, context: AgentContext) -> AgentResult:
        ...

    def build_card(self) -> dict[str, Any]:
        ...


def metric(props: dict[str, Any], key: str) -> float | None:
    value = props.get(key)
    return float(value) if isinstance(value, (int, float)) else None


__all__ = ["AgentCard", "AgentContext", "AgentResult", "MaasAgent", "metric"]
