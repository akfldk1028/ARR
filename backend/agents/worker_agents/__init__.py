"""
Worker Agents Package

Clean, organized structure for all worker agents:
- base/: Base classes and common functionality
- implementations/: Specific worker agent implementations
- cards/: Agent card definitions and templates
- worker_factory.py: Factory for creating workers
- worker_manager.py: Manager for worker lifecycle

Usage:
    from agents.worker_agents import get_worker_for_slug, WorkerAgentFactory
"""

from .base import BaseWorkerAgent
from .worker_factory import WorkerAgentFactory
from .worker_manager import worker_manager, get_worker_for_slug, get_worker_card_for_slug
from .implementations import GeneralWorkerAgent, FlightSpecialistWorkerAgent

__all__ = [
    'BaseWorkerAgent',
    'WorkerAgentFactory',
    'worker_manager',
    'get_worker_for_slug',
    'get_worker_card_for_slug',
    'GeneralWorkerAgent',
    'FlightSpecialistWorkerAgent'
]