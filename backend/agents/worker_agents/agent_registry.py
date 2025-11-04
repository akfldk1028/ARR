"""
Agent Registry - Metadata-driven agent discovery and routing

Provides centralized agent metadata management based on JSON cards.
Eliminates hardcoded agent lists and enables automatic discovery.
"""

import logging
from typing import Dict, List, Set, Optional
from dataclasses import dataclass

from .card_loader import AgentCardLoader

logger = logging.getLogger(__name__)


@dataclass
class AgentMetadata:
    """Agent metadata extracted from JSON card"""
    slug: str
    name: str
    agent_type: str  # "coordinator", "specialist", "orchestrator", etc.
    worker_class: str
    capabilities: Dict[str, bool]

    # Routing configuration
    specialist_threshold: float = 0.70
    general_threshold: float = 0.50
    confidence_gap_threshold: float = 0.01

    @property
    def is_specialist(self) -> bool:
        """Check if this agent is a specialist"""
        return self.agent_type == "specialist"

    @property
    def is_coordinator(self) -> bool:
        """Check if this agent is a coordinator"""
        return self.agent_type == "coordinator"


class AgentRegistry:
    """
    Centralized agent registry with metadata-driven routing

    Features:
    - Auto-discovery from JSON cards
    - Agent type classification (specialist, coordinator, etc.)
    - Routing configuration per agent
    - No hardcoded agent lists
    """

    _registry: Dict[str, AgentMetadata] = {}
    _loaded = False

    @classmethod
    def load_registry(cls, force_reload: bool = False):
        """
        Load agent registry from JSON cards

        Args:
            force_reload: Force reload even if already loaded
        """
        if cls._loaded and not force_reload:
            logger.debug(f"Agent registry already loaded: {len(cls._registry)} agents")
            return

        cls._registry.clear()
        cards = AgentCardLoader.load_all_cards()

        logger.info(f"Building agent registry from {len(cards)} cards...")

        for agent_slug, card in cards.items():
            try:
                django_config = card.get('django', {})
                routing_config = django_config.get('routing_config', {})

                # Extract metadata
                metadata = AgentMetadata(
                    slug=agent_slug,
                    name=card.get('name', agent_slug),
                    agent_type=django_config.get('agent_type', 'custom'),
                    worker_class=django_config.get('worker_class', 'HostAgent'),
                    capabilities=card.get('capabilities', {}),

                    # Routing thresholds (from JSON or defaults)
                    specialist_threshold=routing_config.get('specialist_threshold', 0.70),
                    general_threshold=routing_config.get('general_threshold', 0.50),
                    confidence_gap_threshold=routing_config.get('confidence_gap_threshold', 0.01),
                )

                cls._registry[agent_slug] = metadata

                agent_type_label = "[SPECIALIST]" if metadata.is_specialist else "[COORDINATOR]" if metadata.is_coordinator else "[CUSTOM]"
                logger.info(f"  {agent_type_label}: {agent_slug} -> {metadata.worker_class}")

            except Exception as e:
                logger.error(f"Failed to load metadata for {agent_slug}: {e}")

        cls._loaded = True
        logger.info(f"Agent registry ready: {len(cls._registry)} agents registered")
        logger.info(f"  Specialists: {', '.join(cls.get_specialist_slugs())}")
        logger.info(f"  Coordinators: {', '.join(cls.get_coordinator_slugs())}")

    @classmethod
    def get_metadata(cls, agent_slug: str) -> Optional[AgentMetadata]:
        """
        Get metadata for a specific agent

        Args:
            agent_slug: Agent slug (normalized with hyphens)

        Returns:
            AgentMetadata or None if not found
        """
        if not cls._loaded:
            cls.load_registry()

        return cls._registry.get(agent_slug)

    @classmethod
    def is_specialist(cls, agent_slug: str) -> bool:
        """
        Check if agent is a specialist (based on agent_type in JSON card)

        Args:
            agent_slug: Agent slug

        Returns:
            True if agent_type == "specialist"
        """
        metadata = cls.get_metadata(agent_slug)
        return metadata.is_specialist if metadata else False

    @classmethod
    def is_coordinator(cls, agent_slug: str) -> bool:
        """
        Check if agent is a coordinator

        Args:
            agent_slug: Agent slug

        Returns:
            True if agent_type == "coordinator"
        """
        metadata = cls.get_metadata(agent_slug)
        return metadata.is_coordinator if metadata else False

    @classmethod
    def get_specialist_slugs(cls) -> List[str]:
        """Get list of all specialist agent slugs"""
        if not cls._loaded:
            cls.load_registry()

        return [
            slug for slug, meta in cls._registry.items()
            if meta.is_specialist
        ]

    @classmethod
    def get_coordinator_slugs(cls) -> List[str]:
        """Get list of all coordinator agent slugs"""
        if not cls._loaded:
            cls.load_registry()

        return [
            slug for slug, meta in cls._registry.items()
            if meta.is_coordinator
        ]

    @classmethod
    def get_all_agent_slugs(cls) -> List[str]:
        """Get list of all registered agent slugs"""
        if not cls._loaded:
            cls.load_registry()

        return list(cls._registry.keys())

    @classmethod
    def get_routing_thresholds(cls, agent_slug: str) -> Dict[str, float]:
        """
        Get routing thresholds for an agent

        Args:
            agent_slug: Agent slug

        Returns:
            Dictionary with specialist_threshold, general_threshold, confidence_gap_threshold
        """
        metadata = cls.get_metadata(agent_slug)

        if metadata:
            return {
                'specialist_threshold': metadata.specialist_threshold,
                'general_threshold': metadata.general_threshold,
                'confidence_gap_threshold': metadata.confidence_gap_threshold,
            }

        # Fallback defaults
        return {
            'specialist_threshold': 0.70,
            'general_threshold': 0.50,
            'confidence_gap_threshold': 0.01,
        }

    @classmethod
    def reload(cls):
        """Force reload the registry"""
        logger.info("Reloading agent registry...")
        AgentCardLoader.clear_cache()
        cls.load_registry(force_reload=True)

    @classmethod
    def get_stats(cls) -> Dict[str, any]:
        """Get registry statistics"""
        if not cls._loaded:
            cls.load_registry()

        specialists = cls.get_specialist_slugs()
        coordinators = cls.get_coordinator_slugs()

        return {
            'total_agents': len(cls._registry),
            'specialists': len(specialists),
            'coordinators': len(coordinators),
            'specialist_list': specialists,
            'coordinator_list': coordinators,
        }


# Module-level convenience functions
def is_specialist(agent_slug: str) -> bool:
    """Check if agent is a specialist"""
    return AgentRegistry.is_specialist(agent_slug)


def get_specialist_slugs() -> List[str]:
    """Get all specialist agent slugs"""
    return AgentRegistry.get_specialist_slugs()


def reload_registry():
    """Reload agent registry"""
    AgentRegistry.reload()
