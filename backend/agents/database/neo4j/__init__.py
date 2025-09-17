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

__all__ = [
    # Service functions
    'Neo4jService',
    'get_neo4j_service',
    'initialize_neo4j',
    'shutdown_neo4j',

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