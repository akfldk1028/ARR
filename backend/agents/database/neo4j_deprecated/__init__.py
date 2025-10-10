"""
Neo4j Database Package
Provides graph database functionality for the agent system
"""

from .service import (
    Neo4jService,
    get_neo4j_service,
    initialize_neo4j,
    shutdown_neo4j
)

from .indexes import (
    create_all_indexes,
    get_index_info,
    AGENT_SYSTEM_INDEXES,
    AGENT_SYSTEM_CONSTRAINTS
)

from .stats import (
    get_database_stats,
    get_agent_stats,
    get_conversation_stats,
    get_performance_metrics
)

from .queries import (
    CONVERSATION_QUERIES,
    AGENT_QUERIES,
    WORKER_QUERIES,
    SESSION_QUERIES,
    A2A_QUERIES,
    MAINTENANCE_QUERIES
)

from .conversation_tracker import ConversationTracker
from .task_manager import TaskManager
from .provenance_tracker import ProvenanceTracker
from .governance_manager import GovernanceManager

__all__ = [
    # Service functions
    'Neo4jService',
    'get_neo4j_service',
    'initialize_neo4j',
    'shutdown_neo4j',

    # Conversation tracking
    'ConversationTracker',

    # Task & Contract Net (Phase 2-1)
    'TaskManager',

    # Provenance tracking (Phase 2-2)
    'ProvenanceTracker',

    # Governance & RBAC (Phase 2-3)
    'GovernanceManager',

    # Index functions
    'create_all_indexes',
    'get_index_info',

    # Stats functions
    'get_database_stats',
    'get_agent_stats',
    'get_conversation_stats',
    'get_performance_metrics',

    # Query templates
    'CONVERSATION_QUERIES',
    'AGENT_QUERIES',
    'WORKER_QUERIES',
    'SESSION_QUERIES',
    'A2A_QUERIES',
    'MAINTENANCE_QUERIES',
]