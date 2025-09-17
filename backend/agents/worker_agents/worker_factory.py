"""
Worker Agent Factory
Creates and manages different types of worker agents
"""

import logging
from typing import Dict, Any, Optional, Type

from .base import BaseWorkerAgent
from .implementations import GeneralWorkerAgent, FlightSpecialistWorkerAgent

logger = logging.getLogger(__name__)

class WorkerAgentFactory:
    """Factory for creating worker agents based on agent configuration"""

    # Registry of available worker agent types
    WORKER_TYPES: Dict[str, Type[BaseWorkerAgent]] = {
        'general': GeneralWorkerAgent,
        'flight-specialist': FlightSpecialistWorkerAgent,
        # Add more worker types here as needed
        'test-agent': GeneralWorkerAgent,  # Alias for testing
    }

    @classmethod
    def create_worker(cls, agent_slug: str, agent_config: Dict[str, Any]) -> Optional[BaseWorkerAgent]:
        """Create a worker agent instance based on configuration"""
        try:
            # Determine worker type from config or slug
            worker_type = agent_config.get('agent_type', 'general')

            # Handle slug-based type mapping
            if agent_slug == 'flight-specialist':
                worker_type = 'flight-specialist'
            elif agent_slug == 'test-agent':
                worker_type = 'general'

            # Get worker class
            worker_class = cls.WORKER_TYPES.get(worker_type)
            if not worker_class:
                logger.error(f"Unknown worker type: {worker_type}")
                # Fallback to general worker
                worker_class = GeneralWorkerAgent

            # Create worker instance
            worker = worker_class(agent_slug, agent_config)
            logger.info(f"Created worker agent: {agent_slug} ({worker_class.__name__})")

            return worker

        except Exception as e:
            logger.error(f"Error creating worker agent {agent_slug}: {e}")
            return None

    @classmethod
    def register_worker_type(cls, worker_type: str, worker_class: Type[BaseWorkerAgent]):
        """Register a new worker agent type"""
        cls.WORKER_TYPES[worker_type] = worker_class
        logger.info(f"Registered new worker type: {worker_type}")

    @classmethod
    def get_available_worker_types(cls) -> Dict[str, str]:
        """Get list of available worker types"""
        return {
            worker_type: worker_class.__name__
            for worker_type, worker_class in cls.WORKER_TYPES.items()
        }

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