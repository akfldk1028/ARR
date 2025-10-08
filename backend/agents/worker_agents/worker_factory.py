"""
Worker Agent Factory
Creates and manages different types of worker agents
Dynamically loads worker classes from JSON agent cards
"""

import logging
from typing import Dict, Any, Optional, Type

from .base import BaseWorkerAgent
from .implementations import HostAgent, FlightSpecialistWorkerAgent

logger = logging.getLogger(__name__)

class WorkerAgentFactory:
    """Factory for creating worker agents based on agent configuration"""

    # Registry of available worker agent classes (class name -> class)
    _WORKER_CLASSES: Dict[str, Type[BaseWorkerAgent]] = {
        'HostAgent': HostAgent,
        'FlightSpecialistWorkerAgent': FlightSpecialistWorkerAgent,
    }

    # Runtime registry: agent_slug -> worker_class (populated from JSON cards)
    _WORKER_REGISTRY: Dict[str, Type[BaseWorkerAgent]] = {}
    _registry_loaded = False

    @classmethod
    def _load_worker_registry(cls):
        """Load worker class mappings from JSON agent cards"""
        if cls._registry_loaded:
            return

        from .card_loader import AgentCardLoader

        try:
            logger.info("Loading worker registry from JSON agent cards...")
            cards = AgentCardLoader.load_all_cards()

            for agent_slug, card in cards.items():
                worker_class_name = card.get('django', {}).get('worker_class')

                if not worker_class_name:
                    logger.warning(f"No worker_class specified for {agent_slug}, using HostAgent")
                    worker_class_name = 'HostAgent'

                # Get worker class from registered classes
                worker_class = cls._WORKER_CLASSES.get(worker_class_name)

                if not worker_class:
                    logger.error(f"Worker class '{worker_class_name}' not found for {agent_slug}, using HostAgent")
                    worker_class = cls._WORKER_CLASSES.get('HostAgent')

                cls._WORKER_REGISTRY[agent_slug] = worker_class
                logger.info(f"Registered: {agent_slug} -> {worker_class.__name__}")

            cls._registry_loaded = True
            logger.info(f"Worker registry loaded: {len(cls._WORKER_REGISTRY)} agents")

        except Exception as e:
            logger.error(f"Error loading worker registry: {e}")
            # Fallback to GeneralWorkerAgent
            cls._WORKER_REGISTRY = {}

    @classmethod
    def create_worker(cls, agent_slug: str, agent_config: Dict[str, Any]) -> Optional[BaseWorkerAgent]:
        """Create a worker agent instance based on configuration"""
        try:
            # Load registry from JSON cards if not loaded
            if not cls._registry_loaded:
                cls._load_worker_registry()

            # Get worker class from registry
            worker_class = cls._WORKER_REGISTRY.get(agent_slug)

            if not worker_class:
                logger.warning(f"No worker class registered for {agent_slug}, using HostAgent")
                worker_class = cls._WORKER_CLASSES.get('HostAgent')

            if not worker_class:
                logger.error(f"Could not create worker for {agent_slug}")
                return None

            # Create worker instance
            worker = worker_class(agent_slug, agent_config)
            logger.info(f"Created worker agent: {agent_slug} ({worker_class.__name__})")

            return worker

        except Exception as e:
            logger.error(f"Error creating worker agent {agent_slug}: {e}")
            return None

    @classmethod
    def register_worker_class(cls, class_name: str, worker_class: Type[BaseWorkerAgent]):
        """Register a new worker agent class for dynamic loading"""
        cls._WORKER_CLASSES[class_name] = worker_class
        logger.info(f"Registered new worker class: {class_name}")
        # Force reload of registry to pick up new class
        cls._registry_loaded = False

    @classmethod
    def get_available_worker_types(cls) -> Dict[str, str]:
        """Get list of available worker types from registry"""
        if not cls._registry_loaded:
            cls._load_worker_registry()

        return {
            agent_slug: worker_class.__name__
            for agent_slug, worker_class in cls._WORKER_REGISTRY.items()
        }

    @classmethod
    def reload_registry(cls):
        """Force reload of worker registry from JSON cards"""
        cls._registry_loaded = False
        cls._WORKER_REGISTRY = {}
        cls._load_worker_registry()

    @classmethod
    def create_worker_from_django_model(cls, agent_model) -> Optional[BaseWorkerAgent]:
        """Create worker from Django Agent model"""
        try:
            agent_config = {
                'name': agent_model.name,
                'description': agent_model.description,
                'agent_type': agent_model.agent_type,
                'model_name': agent_model.model_name,
                'system_prompt': agent_model.system_prompt,
                'capabilities': agent_model.capabilities,
                'config': agent_model.config or {},
                'rate_limit_per_minute': agent_model.rate_limit_per_minute,
                'max_concurrent_sessions': agent_model.max_concurrent_sessions
            }

            return cls.create_worker(agent_model.slug, agent_config)

        except Exception as e:
            logger.error(f"Error creating worker from Django model: {e}")
            return None