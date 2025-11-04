"""
Law Domain Agent Package

Provides Multi-Agent System (MAS) for Korean law:
- AgentManager: Self-organizing domain manager
- DomainAgent: Domain-specific worker agent
"""

from .agent_manager import AgentManager, DomainInfo
from .domain_agent import DomainAgent

__all__ = ['AgentManager', 'DomainInfo', 'DomainAgent']
