"""
Worker Agent Manager
Manages lifecycle and registry of all worker agents
"""

import logging
from typing import Dict, Optional
from asgiref.sync import sync_to_async

from .base import BaseWorkerAgent
from .worker_factory import WorkerAgentFactory

logger = logging.getLogger(__name__)

class WorkerAgentManager:
    """Manages all active worker agents"""

    def __init__(self):
        self._workers: Dict[str, BaseWorkerAgent] = {}

    async def get_worker(self, agent_slug: str) -> Optional[BaseWorkerAgent]:
        """Get or create worker agent by slug"""

        # Return cached worker if exists
        if agent_slug in self._workers:
            return self._workers[agent_slug]

        # Try to create from Django model first
        try:
            from django.core.asgi import get_asgi_application
            from agents.models import Agent

            # Use sync_to_async for Django ORM operations
            get_agent = sync_to_async(Agent.objects.get)
            agent_model = await get_agent(slug=agent_slug, status='active')

            # Create worker from model
            worker = WorkerAgentFactory.create_worker_from_django_model(agent_model)

            if worker:
                self._workers[agent_slug] = worker
                logger.info(f"Created and cached worker from Django model: {agent_slug}")
                return worker
            else:
                logger.error(f"Failed to create worker from Django model for {agent_slug}")
                # Fall through to JSON card loading
        except Exception as e:
            logger.warning(f"Django model not found for {agent_slug}: {e}, trying JSON card...")

        # Fallback: Try to create from JSON card
        try:
            from .card_loader import AgentCardLoader

            # Load JSON card
            cards = AgentCardLoader.load_all_cards()
            agent_config = cards.get(agent_slug)

            if agent_config:
                # Create worker from JSON card config
                worker = WorkerAgentFactory.create_worker(agent_slug, agent_config)

                if worker:
                    self._workers[agent_slug] = worker
                    logger.info(f"Created and cached worker from JSON card: {agent_slug}")
                    return worker
                else:
                    logger.error(f"Failed to create worker from JSON card for {agent_slug}")
                    return None
            else:
                logger.error(f"No JSON card found for {agent_slug}")
                return None

        except Exception as e:
            logger.error(f"Error loading worker from JSON card for {agent_slug}: {e}")
            return None

    def register_worker(self, agent_slug: str, worker: BaseWorkerAgent):
        """Manually register a worker agent"""
        self._workers[agent_slug] = worker
        logger.info(f"Manually registered worker: {agent_slug}")

    def remove_worker(self, agent_slug: str):
        """Remove worker from registry"""
        if agent_slug in self._workers:
            del self._workers[agent_slug]
            logger.info(f"Removed worker: {agent_slug}")

    def list_active_workers(self) -> Dict[str, str]:
        """List all active workers"""
        return {
            slug: worker.agent_name
            for slug, worker in self._workers.items()
        }

    def clear_all_workers(self):
        """Clear all worker agents (useful for testing/restart)"""
        self._workers.clear()
        logger.info("Cleared all worker agents")

    async def get_worker_card(self, agent_slug: str) -> Optional[Dict]:
        """Get agent card for worker"""
        worker = await self.get_worker(agent_slug)
        if worker:
            return worker.generate_agent_card()
        return None

    async def reload_worker(self, agent_slug: str) -> bool:
        """Reload worker from database (useful after config changes)"""
        try:
            # Remove cached worker
            if agent_slug in self._workers:
                del self._workers[agent_slug]

            # Get fresh worker
            worker = await self.get_worker(agent_slug)
            return worker is not None

        except Exception as e:
            logger.error(f"Error reloading worker {agent_slug}: {e}")
            return False

# Global worker manager instance
worker_manager = WorkerAgentManager()

# Convenience functions for external use
async def get_worker_for_slug(agent_slug: str) -> Optional[BaseWorkerAgent]:
    """Get worker agent for given slug"""
    return await worker_manager.get_worker(agent_slug)

async def get_worker_card_for_slug(agent_slug: str) -> Optional[Dict]:
    """Get agent card for given slug"""
    return await worker_manager.get_worker_card(agent_slug)