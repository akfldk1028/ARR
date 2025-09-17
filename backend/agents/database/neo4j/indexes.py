"""
Neo4j Index Management
Creates and manages database indexes for optimal performance
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# Index definitions for the agent system
AGENT_SYSTEM_INDEXES = [
    # User and session indexes
    "CREATE INDEX user_session_idx IF NOT EXISTS FOR (u:User) ON (u.session_id)",
    "CREATE INDEX user_name_idx IF NOT EXISTS FOR (u:User) ON (u.name)",

    # Agent indexes
    "CREATE INDEX agent_name_idx IF NOT EXISTS FOR (a:Agent) ON (a.name)",
    "CREATE INDEX agent_slug_idx IF NOT EXISTS FOR (a:Agent) ON (a.slug)",
    "CREATE INDEX agent_type_idx IF NOT EXISTS FOR (a:Agent) ON (a.type)",

    # Conversation and context indexes
    "CREATE INDEX conversation_id_idx IF NOT EXISTS FOR (c:Conversation) ON (c.conversation_id)",
    "CREATE INDEX context_id_idx IF NOT EXISTS FOR (c:Context) ON (c.context_id)",
    "CREATE INDEX session_id_idx IF NOT EXISTS FOR (s:Session) ON (s.session_id)",

    # Message indexes
    "CREATE INDEX message_timestamp_idx IF NOT EXISTS FOR (m:Message) ON (m.timestamp)",
    "CREATE INDEX message_type_idx IF NOT EXISTS FOR (m:Message) ON (m.type)",
    "CREATE INDEX message_id_idx IF NOT EXISTS FOR (m:Message) ON (m.id)",

    # Worker agent specific indexes
    "CREATE INDEX worker_agent_slug_idx IF NOT EXISTS FOR (w:WorkerAgent) ON (w.slug)",
    "CREATE INDEX worker_capability_idx IF NOT EXISTS FOR (c:Capability) ON (c.name)",

    # A2A communication indexes
    "CREATE INDEX a2a_message_id_idx IF NOT EXISTS FOR (a:A2AMessage) ON (a.messageId)",
    "CREATE INDEX a2a_context_idx IF NOT EXISTS FOR (a:A2AMessage) ON (a.contextId)",
]

# Constraint definitions for data integrity
AGENT_SYSTEM_CONSTRAINTS = [
    # Unique constraints
    "CREATE CONSTRAINT agent_slug_unique IF NOT EXISTS FOR (a:Agent) REQUIRE a.slug IS UNIQUE",
    "CREATE CONSTRAINT user_session_unique IF NOT EXISTS FOR (u:User) REQUIRE u.session_id IS UNIQUE",
    "CREATE CONSTRAINT conversation_id_unique IF NOT EXISTS FOR (c:Conversation) REQUIRE c.conversation_id IS UNIQUE",
    "CREATE CONSTRAINT message_id_unique IF NOT EXISTS FOR (m:Message) REQUIRE m.id IS UNIQUE",
]

def create_index(service, index_query: str) -> bool:
    """Create a single index"""
    try:
        service.execute_write_query(index_query)
        logger.info(f"✅ Index created/verified: {index_query[:50]}...")
        return True
    except Exception as e:
        # Neo4j returns error if index already exists, which is okay
        if "already exists" in str(e).lower():
            logger.debug(f"Index already exists: {index_query[:50]}...")
        else:
            logger.warning(f"⚠️ Index creation warning: {str(e)}")
        return False

def create_constraint(service, constraint_query: str) -> bool:
    """Create a single constraint"""
    try:
        service.execute_write_query(constraint_query)
        logger.info(f"✅ Constraint created/verified: {constraint_query[:50]}...")
        return True
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.debug(f"Constraint already exists: {constraint_query[:50]}...")
        else:
            logger.warning(f"⚠️ Constraint creation warning: {str(e)}")
        return False

def create_all_indexes(service) -> dict:
    """Create all indexes for the agent system"""
    results = {
        "indexes_created": 0,
        "indexes_failed": 0,
        "constraints_created": 0,
        "constraints_failed": 0
    }

    logger.info("Creating Neo4j indexes...")

    # Create indexes
    for index_query in AGENT_SYSTEM_INDEXES:
        if create_index(service, index_query):
            results["indexes_created"] += 1
        else:
            results["indexes_failed"] += 1

    # Create constraints
    for constraint_query in AGENT_SYSTEM_CONSTRAINTS:
        if create_constraint(service, constraint_query):
            results["constraints_created"] += 1
        else:
            results["constraints_failed"] += 1

    logger.info(f"Index creation complete: {results}")
    return results

def drop_all_indexes(service) -> bool:
    """Drop all indexes (use with caution!)"""
    try:
        # Get all indexes
        indexes = service.execute_query("SHOW INDEXES")

        for index in indexes:
            index_name = index.get('name')
            if index_name:
                drop_query = f"DROP INDEX {index_name}"
                service.execute_write_query(drop_query)
                logger.info(f"Dropped index: {index_name}")

        return True
    except Exception as e:
        logger.error(f"Error dropping indexes: {e}")
        return False

def get_index_info(service) -> List[dict]:
    """Get information about all indexes"""
    try:
        return service.execute_query("SHOW INDEXES")
    except Exception as e:
        logger.error(f"Error getting index info: {e}")
        return []