"""Deterministic agent contracts for interactive MAAS.

These are lightweight local agents for now. They make the multi-agent handoff
explicit without requiring an LLM call on every geometry drag.
"""

from .a2ui_surface import ARR_MAAS_CATALOG_ID, build_agent_review_a2ui_messages
from .contracts import build_agent_cards, build_agent_registry, build_agent_reviews

__all__ = [
    "ARR_MAAS_CATALOG_ID",
    "build_agent_cards",
    "build_agent_registry",
    "build_agent_review_a2ui_messages",
    "build_agent_reviews",
]
