"""
Neo4j Database Statistics
Provides database statistics and monitoring functions
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def get_database_stats(service) -> Dict[str, Any]:
    """Get comprehensive database statistics"""
    stats = {}

    try:
        # Basic counts
        stats["total_nodes"] = get_node_count(service)
        stats["total_relationships"] = get_relationship_count(service)

        # Node statistics by label
        stats["nodes_by_label"] = get_nodes_by_label(service)

        # Relationship statistics by type
        stats["relationships_by_type"] = get_relationships_by_type(service)

        # Agent-specific stats
        stats["agent_stats"] = get_agent_stats(service)

        # Conversation stats
        stats["conversation_stats"] = get_conversation_stats(service)

        # Database metadata
        stats["labels"] = get_all_labels(service)
        stats["relationship_types"] = get_all_relationship_types(service)

    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        stats["error"] = str(e)

    return stats

def get_node_count(service) -> int:
    """Get total number of nodes"""
    result = service.execute_query("MATCH (n) RETURN count(n) as count")
    return result[0]["count"] if result else 0

def get_relationship_count(service) -> int:
    """Get total number of relationships"""
    result = service.execute_query("MATCH ()-[r]->() RETURN count(r) as count")
    return result[0]["count"] if result else 0

def get_nodes_by_label(service) -> Dict[str, int]:
    """Get node count by label"""
    nodes_by_label = {}

    # Get all labels
    labels = get_all_labels(service)

    for label in labels:
        query = f"MATCH (n:{label}) RETURN count(n) as count"
        result = service.execute_query(query)
        nodes_by_label[label] = result[0]["count"] if result else 0

    return nodes_by_label

def get_relationships_by_type(service) -> Dict[str, int]:
    """Get relationship count by type"""
    relationships_by_type = {}

    # Get all relationship types
    rel_types = get_all_relationship_types(service)

    for rel_type in rel_types:
        query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
        result = service.execute_query(query)
        relationships_by_type[rel_type] = result[0]["count"] if result else 0

    return relationships_by_type

def get_all_labels(service) -> List[str]:
    """Get all node labels in the database"""
    result = service.execute_query("CALL db.labels()")
    return [record["label"] for record in result] if result else []

def get_all_relationship_types(service) -> List[str]:
    """Get all relationship types in the database"""
    result = service.execute_query("CALL db.relationshipTypes()")
    return [record["relationshipType"] for record in result] if result else []

def get_agent_stats(service) -> Dict[str, Any]:
    """Get agent-specific statistics"""
    agent_stats = {}

    try:
        # Total agents
        result = service.execute_query("MATCH (a:Agent) RETURN count(a) as count")
        agent_stats["total_agents"] = result[0]["count"] if result else 0

        # Agents by type
        result = service.execute_query("""
            MATCH (a:Agent)
            RETURN a.type as type, count(a) as count
            ORDER BY count DESC
        """)
        agent_stats["by_type"] = {r["type"]: r["count"] for r in result} if result else {}

        # Active agents
        result = service.execute_query("""
            MATCH (a:Agent {status: 'active'})
            RETURN count(a) as count
        """)
        agent_stats["active_agents"] = result[0]["count"] if result else 0

    except Exception as e:
        logger.error(f"Error getting agent stats: {e}")
        agent_stats["error"] = str(e)

    return agent_stats

def get_conversation_stats(service) -> Dict[str, Any]:
    """Get conversation-specific statistics"""
    conv_stats = {}

    try:
        # Total conversations
        result = service.execute_query("MATCH (c:Conversation) RETURN count(c) as count")
        conv_stats["total_conversations"] = result[0]["count"] if result else 0

        # Total messages
        result = service.execute_query("MATCH (m:Message) RETURN count(m) as count")
        conv_stats["total_messages"] = result[0]["count"] if result else 0

        # Messages by type
        result = service.execute_query("""
            MATCH (m:Message)
            RETURN m.type as type, count(m) as count
            ORDER BY count DESC
        """)
        conv_stats["messages_by_type"] = {r["type"]: r["count"] for r in result} if result else {}

        # Recent activity (last 24 hours)
        result = service.execute_query("""
            MATCH (m:Message)
            WHERE m.timestamp > datetime() - duration({hours: 24})
            RETURN count(m) as count
        """)
        conv_stats["messages_last_24h"] = result[0]["count"] if result else 0

    except Exception as e:
        logger.error(f"Error getting conversation stats: {e}")
        conv_stats["error"] = str(e)

    return conv_stats

def get_performance_metrics(service) -> Dict[str, Any]:
    """Get database performance metrics"""
    metrics = {}

    try:
        # Get database size
        result = service.execute_query("""
            CALL dbms.database.info() YIELD name, totalSize
            RETURN name, totalSize
        """)
        if result:
            metrics["database_size"] = result[0]["totalSize"]

        # Get memory usage (if available)
        result = service.execute_query("""
            CALL dbms.components() YIELD name, versions, edition
            RETURN name, versions, edition
        """)
        metrics["neo4j_version"] = result[0] if result else {}

    except Exception as e:
        logger.debug(f"Some metrics not available: {e}")

    return metrics