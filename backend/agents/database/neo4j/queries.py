"""
Neo4j Query Templates
Common Cypher query templates for the agent system
"""

# Conversation Management Queries
CONVERSATION_QUERIES = {
    "create_conversation": """
        MERGE (c:Conversation {conversation_id: $conversation_id})
        SET c.session_id = $session_id,
            c.created_at = coalesce(c.created_at, $timestamp),
            c.updated_at = $timestamp,
            c.message_count = coalesce(c.message_count, 0)
        RETURN c
    """,

    "create_message": """
        MATCH (c:Conversation {conversation_id: $conversation_id})
        CREATE (m:Message {
            id: $message_id,
            type: $message_type,
            content: $content,
            timestamp: $timestamp,
            session_id: $session_id,
            user_name: $user_name,
            agent_slug: $agent_slug
        })
        CREATE (c)-[:HAS_MESSAGE]->(m)
        SET c.message_count = c.message_count + 1,
            c.updated_at = $timestamp
        RETURN m
    """,

    "get_conversation_history": """
        MATCH (c:Conversation {conversation_id: $conversation_id})-[:HAS_MESSAGE]->(m:Message)
        RETURN m.id as id,
               m.type as type,
               m.content as content,
               m.timestamp as timestamp,
               m.user_name as user_name,
               m.agent_slug as agent_slug
        ORDER BY m.timestamp ASC
        SKIP $skip
        LIMIT $limit
    """,

    "delete_conversation": """
        MATCH (c:Conversation {conversation_id: $conversation_id})
        OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
        DETACH DELETE c, m
    """
}

# Agent Management Queries
AGENT_QUERIES = {
    "create_agent_node": """
        MERGE (a:Agent {slug: $slug})
        SET a.name = $name,
            a.type = $agent_type,
            a.description = $description,
            a.status = $status,
            a.created_at = coalesce(a.created_at, $timestamp),
            a.updated_at = $timestamp
        RETURN a
    """,

    "get_agent_by_slug": """
        MATCH (a:Agent {slug: $slug})
        RETURN a.slug as slug,
               a.name as name,
               a.type as type,
               a.description as description,
               a.status as status
    """,

    "update_agent_status": """
        MATCH (a:Agent {slug: $slug})
        SET a.status = $status,
            a.updated_at = $timestamp
        RETURN a
    """,

    "get_active_agents": """
        MATCH (a:Agent {status: 'active'})
        RETURN a.slug as slug,
               a.name as name,
               a.type as type
        ORDER BY a.name
    """
}

# Worker Agent Communication Queries
WORKER_QUERIES = {
    "record_worker_communication": """
        MATCH (source:Agent {slug: $source_slug}), (target:Agent {slug: $target_slug})
        CREATE (comm:Communication {
            id: $communication_id,
            timestamp: $timestamp,
            context_id: $context_id,
            message: $message,
            response: $response
        })
        CREATE (source)-[:SENT_TO]->(comm)-[:RECEIVED_BY]->(target)
        RETURN comm
    """,

    "get_worker_communications": """
        MATCH (source:Agent)-[:SENT_TO]->(comm:Communication)-[:RECEIVED_BY]->(target:Agent)
        WHERE source.slug = $agent_slug OR target.slug = $agent_slug
        RETURN source.slug as source,
               target.slug as target,
               comm.timestamp as timestamp,
               comm.message as message,
               comm.response as response
        ORDER BY comm.timestamp DESC
        LIMIT $limit
    """
}

# Session Management Queries (Legacy: using Conversation node for consistency)
SESSION_QUERIES = {
    "create_session": """
        MERGE (s:Conversation {session_id: $session_id})
        MERGE (c:Context {context_id: $context_id})
        MERGE (s)-[:IN_CONTEXT]->(c)
        SET s.created_at = coalesce(s.created_at, $timestamp),
            s.updated_at = $timestamp,
            s.user_name = coalesce(s.user_name, $user_name)
        RETURN s, c
    """,

    "save_session_message": """
        MERGE (s:Conversation {session_id: $session_id})
        MERGE (c:Context {context_id: $context_id})
        MERGE (s)-[:IN_CONTEXT]->(c)
        CREATE (m:Message {
            id: $message_id,
            type: $message_type,
            content: $content,
            user_name: $user_name,
            agent_slug: $agent_slug,
            timestamp: $timestamp
        })
        CREATE (s)-[:HAS_MESSAGE]->(m)
        RETURN m
    """,

    "get_session_history": """
        MATCH (s:Conversation {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
        WHERE m.agent_slug = $agent_slug OR m.type = 'user'
        RETURN m.content as content,
               m.type as role,
               m.timestamp as timestamp
        ORDER BY m.timestamp DESC
        LIMIT $limit
    """
}

# A2A Protocol Queries
A2A_QUERIES = {
    "record_a2a_message": """
        CREATE (msg:A2AMessage {
            messageId: $messageId,
            contextId: $contextId,
            role: $role,
            content: $content,
            timestamp: $timestamp,
            source_agent: $source_agent,
            target_agent: $target_agent
        })
        RETURN msg
    """,

    "get_a2a_context": """
        MATCH (msg:A2AMessage {contextId: $contextId})
        RETURN msg.messageId as messageId,
               msg.role as role,
               msg.content as content,
               msg.timestamp as timestamp
        ORDER BY msg.timestamp ASC
    """
}

# Cleanup and Maintenance Queries
MAINTENANCE_QUERIES = {
    "delete_old_messages": """
        MATCH (m:Message)
        WHERE m.timestamp < $cutoff_timestamp
        DETACH DELETE m
    """,

    "cleanup_orphan_nodes": """
        MATCH (n)
        WHERE NOT (n)--()
        DELETE n
    """,

    "get_database_size": """
        MATCH (n)
        RETURN count(n) as node_count,
               size((n)--()) as relationship_count
    """
}