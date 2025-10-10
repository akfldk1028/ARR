"""
Neo4j Conversation Tracker
Enterprise-grade conversation tracking for multi-agent system
Implements the Neo4j Enterprise Schema for Session/Turn/Message/Agent tracking
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
import json

from graph_db.services import Neo4jService

logger = logging.getLogger(__name__)


class ConversationTracker:
    """Tracks conversations, turns, messages, and agent executions in Neo4j"""

    def __init__(self, service: Neo4jService):
        self.service = service

    def get_or_create_conversation(self, user_id: str, browser_session_id: str, metadata: Dict[str, Any] = None) -> str:
        """Get existing active conversation or create new one"""
        # 1. 기존 활성 Conversation 검색
        search_query = """
        MATCH (c:Conversation {user_id: $user_id, status: 'active'})
        WHERE c.metadata CONTAINS $browser_session_id
        RETURN c.id as conversation_id
        ORDER BY c.started_at DESC
        LIMIT 1
        """

        search_params = {
            'user_id': user_id,
            'browser_session_id': browser_session_id
        }

        result = self.service.execute_query(search_query, search_params)

        if result and len(result) > 0:
            conversation_id = result[0]['conversation_id']
            logger.info(f"Reusing existing conversation {conversation_id} for user {user_id}")
            return conversation_id

        # 2. 없으면 새로 생성
        return self.create_conversation(user_id, metadata)

    def create_conversation(self, user_id: str, metadata: Dict[str, Any] = None) -> str:
        """Create a new conversation"""
        conversation_id = str(uuid4())
        metadata = metadata or {}

        # Extract key fields as properties, rest as JSON string
        django_session_id = metadata.get('django_session_id', '')
        current_agent = metadata.get('agent', 'hostagent')

        query = """
        MERGE (u:User {id: $user_id})
        CREATE (c:Conversation {
            id: $conversation_id,
            user_id: $user_id,
            django_session_id: $django_session_id,
            current_agent: $current_agent,
            started_at: datetime($started_at),
            status: 'active',
            metadata_json: $metadata_json
        })
        CREATE (u)-[:STARTED_CONVERSATION]->(c)
        RETURN c.id as conversation_id
        """

        params = {
            'conversation_id': conversation_id,
            'user_id': user_id,
            'django_session_id': django_session_id,
            'current_agent': current_agent,
            'started_at': datetime.utcnow().isoformat(),
            'metadata_json': json.dumps(metadata)  # Full metadata as JSON string
        }

        result = self.service.execute_write_query(query, params)
        logger.info(f"Created conversation {conversation_id} for user {user_id}")
        return conversation_id

    def create_turn(self, conversation_id: str, sequence: int, user_query: str) -> str:
        """Create a new conversation turn"""
        turn_id = str(uuid4())
        query = """
        MATCH (c:Conversation {id: $conversation_id})
        CREATE (t:Turn {
            id: $turn_id,
            conversation_id: $conversation_id,
            sequence: $sequence,
            started_at: datetime($started_at),
            user_query: $user_query
        })
        CREATE (c)-[:HAS_TURN]->(t)
        RETURN t.id as turn_id
        """

        params = {
            'turn_id': turn_id,
            'conversation_id': conversation_id,
            'sequence': sequence,
            'started_at': datetime.utcnow().isoformat(),
            'user_query': user_query
        }

        result = self.service.execute_write_query(query, params)
        logger.info(f"Created turn {turn_id} for conversation {conversation_id}")
        return turn_id

    def add_message(
        self,
        conversation_id: str,
        turn_id: str,
        role: str,
        content: str,
        sequence: int,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Add a message to a turn"""
        message_id = str(uuid4())
        metadata = metadata or {}

        query = """
        MATCH (t:Turn {id: $turn_id})
        CREATE (m:Message {
            id: $message_id,
            conversation_id: $conversation_id,
            turn_id: $turn_id,
            role: $role,
            content: $content,
            timestamp: datetime($timestamp),
            sequence: $sequence,
            metadata_json: $metadata_json
        })
        CREATE (t)-[:HAS_MESSAGE]->(m)
        RETURN m.id as message_id
        """

        params = {
            'message_id': message_id,
            'conversation_id': conversation_id,
            'turn_id': turn_id,
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat(),
            'sequence': sequence,
            'metadata_json': json.dumps(metadata)  # Full metadata as JSON string
        }

        result = self.service.execute_write_query(query, params)
        logger.debug(f"Added {role} message {message_id} to turn {turn_id}")
        return message_id

    def create_agent_execution(
        self,
        agent_slug: str,
        turn_id: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create an agent execution record"""
        execution_id = str(uuid4())
        metadata = metadata or {}

        query = """
        MATCH (t:Turn {id: $turn_id})
        MATCH (a:Agent {slug: $agent_slug})
        CREATE (ae:AgentExecution {
            id: $execution_id,
            agent_slug: $agent_slug,
            turn_id: $turn_id,
            started_at: datetime($started_at),
            status: 'processing',
            metadata_json: $metadata_json
        })
        CREATE (t)-[:EXECUTED_BY]->(ae)
        CREATE (ae)-[:USED_AGENT]->(a)
        RETURN ae.id as execution_id
        """

        params = {
            'execution_id': execution_id,
            'agent_slug': agent_slug,
            'turn_id': turn_id,
            'started_at': datetime.utcnow().isoformat(),
            'metadata_json': json.dumps(metadata)  # Full metadata as JSON string
        }

        result = self.service.execute_write_query(query, params)
        logger.info(f"Created agent execution {execution_id} for {agent_slug}")
        return execution_id

    def complete_agent_execution(
        self,
        execution_id: str,
        status: str = 'completed',
        error_message: str = None
    ):
        """Mark an agent execution as completed"""
        query = """
        MATCH (ae:AgentExecution {id: $execution_id})
        SET ae.completed_at = datetime($completed_at),
            ae.status = $status,
            ae.execution_time_ms = duration.between(ae.started_at, datetime($completed_at)).milliseconds,
            ae.error_message = $error_message
        RETURN ae
        """

        params = {
            'execution_id': execution_id,
            'completed_at': datetime.utcnow().isoformat(),
            'status': status,
            'error_message': error_message
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Completed agent execution {execution_id} with status {status}")

    def create_delegation(
        self,
        from_execution_id: str,
        to_execution_id: str,
        reason: str,
        semantic_score: float = None,
        skill_matched: str = None,
        decision_time_ms: int = None
    ):
        """Create a delegation relationship between agent executions"""
        query = """
        MATCH (from:AgentExecution {id: $from_execution_id})
        MATCH (to:AgentExecution {id: $to_execution_id})
        CREATE (from)-[d:DELEGATED_TO {
            reason: $reason,
            semantic_score: $semantic_score,
            skill_matched: $skill_matched,
            decision_time_ms: $decision_time_ms,
            delegated_at: datetime($delegated_at)
        }]->(to)
        RETURN d
        """

        params = {
            'from_execution_id': from_execution_id,
            'to_execution_id': to_execution_id,
            'reason': reason,
            'semantic_score': semantic_score,
            'skill_matched': skill_matched,
            'decision_time_ms': decision_time_ms,
            'delegated_at': datetime.utcnow().isoformat()
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Created delegation from {from_execution_id} to {to_execution_id}")

    def complete_turn(self, turn_id: str):
        """Mark a turn as completed"""
        query = """
        MATCH (t:Turn {id: $turn_id})
        SET t.completed_at = datetime($completed_at)
        RETURN t
        """

        params = {
            'turn_id': turn_id,
            'completed_at': datetime.utcnow().isoformat()
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Completed turn {turn_id}")

    def complete_conversation(self, conversation_id: str, status: str = 'completed'):
        """Mark a conversation as completed"""
        query = """
        MATCH (c:Conversation {id: $conversation_id})
        SET c.ended_at = datetime($ended_at),
            c.status = $status
        RETURN c
        """

        params = {
            'conversation_id': conversation_id,
            'ended_at': datetime.utcnow().isoformat(),
            'status': status
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Completed conversation {conversation_id} with status {status}")

    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """Get conversation history"""
        query = """
        MATCH (c:Conversation {id: $conversation_id})-[:HAS_TURN]->(t:Turn)
        MATCH (t)-[:INCLUDES_MESSAGE]->(m:Message)
        RETURN t.sequence as turn_sequence,
               m.sequence as message_sequence,
               m.role as role,
               m.content as content,
               m.timestamp as timestamp
        ORDER BY t.sequence, m.sequence
        LIMIT $limit
        """

        params = {
            'conversation_id': conversation_id,
            'limit': limit
        }

        return self.service.execute_query(query, params)

    def get_agent_performance_stats(self, agent_slug: str) -> Dict[str, Any]:
        """Get performance statistics for an agent"""
        query = """
        MATCH (ae:AgentExecution {agent_slug: $agent_slug})
        WHERE ae.status = 'completed'
        RETURN
            count(ae) as total_executions,
            avg(ae.execution_time_ms) as avg_execution_time_ms,
            min(ae.execution_time_ms) as min_execution_time_ms,
            max(ae.execution_time_ms) as max_execution_time_ms
        """

        params = {'agent_slug': agent_slug}
        result = self.service.execute_query(query, params)

        if result:
            return result[0]
        return {}

    def get_delegation_chain(self, turn_id: str) -> List[Dict]:
        """Get the delegation chain for a turn"""
        query = """
        MATCH (t:Turn {id: $turn_id})-[:EXECUTED_BY]->(ae:AgentExecution)
        OPTIONAL MATCH path = (ae)-[:DELEGATED_TO*]->(other:AgentExecution)
        RETURN ae.agent_slug as agent_slug,
               ae.status as status,
               ae.started_at as started_at,
               ae.completed_at as completed_at,
               collect(other.agent_slug) as delegated_to
        """

        params = {'turn_id': turn_id}
        return self.service.execute_query(query, params)

    def get_last_turn_sequence(self, conversation_id: str) -> int:
        """Get the last Turn sequence number for a Conversation"""
        query = """
        MATCH (c:Conversation {id: $conversation_id})-[:HAS_TURN]->(t:Turn)
        RETURN t.sequence as sequence
        ORDER BY t.sequence DESC
        LIMIT 1
        """

        params = {'conversation_id': conversation_id}
        result = self.service.execute_query(query, params)

        if result and len(result) > 0:
            last_sequence = result[0]['sequence']
            logger.debug(f"Last Turn sequence for conversation {conversation_id}: {last_sequence}")
            return last_sequence

        logger.debug(f"No Turns found for conversation {conversation_id}, starting at 0")
        return 0
