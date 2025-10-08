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

from .service import Neo4jService

logger = logging.getLogger(__name__)


class ConversationTracker:
    """Tracks conversations, turns, messages, and agent executions in Neo4j"""

    def __init__(self, service: Neo4jService):
        self.service = service

    def create_session(self, user_id: str, metadata: Dict[str, Any] = None) -> str:
        """Create a new conversation session"""
        session_id = str(uuid4())
        query = """
        MERGE (u:User {id: $user_id})
        CREATE (s:Session {
            id: $session_id,
            user_id: $user_id,
            started_at: datetime($started_at),
            status: 'active',
            metadata: $metadata
        })
        CREATE (u)-[:STARTED_SESSION]->(s)
        RETURN s.id as session_id
        """

        params = {
            'session_id': session_id,
            'user_id': user_id,
            'started_at': datetime.utcnow().isoformat(),
            'metadata': json.dumps(metadata or {})
        }

        result = self.service.execute_write_query(query, params)
        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id

    def create_turn(self, session_id: str, sequence: int, user_query: str) -> str:
        """Create a new conversation turn"""
        turn_id = str(uuid4())
        query = """
        MATCH (s:Session {id: $session_id})
        CREATE (t:Turn {
            id: $turn_id,
            session_id: $session_id,
            sequence: $sequence,
            started_at: datetime($started_at),
            user_query: $user_query
        })
        CREATE (s)-[:HAS_TURN]->(t)
        RETURN t.id as turn_id
        """

        params = {
            'turn_id': turn_id,
            'session_id': session_id,
            'sequence': sequence,
            'started_at': datetime.utcnow().isoformat(),
            'user_query': user_query
        }

        result = self.service.execute_write_query(query, params)
        logger.info(f"Created turn {turn_id} for session {session_id}")
        return turn_id

    def add_message(
        self,
        session_id: str,
        turn_id: str,
        role: str,
        content: str,
        sequence: int,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Add a message to a turn"""
        message_id = str(uuid4())
        query = """
        MATCH (t:Turn {id: $turn_id})
        CREATE (m:Message {
            id: $message_id,
            session_id: $session_id,
            turn_id: $turn_id,
            role: $role,
            content: $content,
            timestamp: datetime($timestamp),
            sequence: $sequence,
            metadata: $metadata
        })
        CREATE (t)-[:HAS_MESSAGE]->(m)
        RETURN m.id as message_id
        """

        params = {
            'message_id': message_id,
            'session_id': session_id,
            'turn_id': turn_id,
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat(),
            'sequence': sequence,
            'metadata': json.dumps(metadata or {})
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
        query = """
        MATCH (t:Turn {id: $turn_id})
        MATCH (a:Agent {slug: $agent_slug})
        CREATE (ae:AgentExecution {
            id: $execution_id,
            agent_slug: $agent_slug,
            turn_id: $turn_id,
            started_at: datetime($started_at),
            status: 'processing',
            metadata: $metadata
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
            'metadata': json.dumps(metadata or {})
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

    def complete_session(self, session_id: str, status: str = 'completed'):
        """Mark a session as completed"""
        query = """
        MATCH (s:Session {id: $session_id})
        SET s.ended_at = datetime($ended_at),
            s.status = $status
        RETURN s
        """

        params = {
            'session_id': session_id,
            'ended_at': datetime.utcnow().isoformat(),
            'status': status
        }

        self.service.execute_write_query(query, params)
        logger.info(f"Completed session {session_id} with status {status}")

    def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Get conversation history for a session"""
        query = """
        MATCH (s:Session {id: $session_id})-[:HAS_TURN]->(t:Turn)
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
            'session_id': session_id,
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
