"""
Base Worker Agent Class
Provides common functionality for all worker agents
"""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime

from django.conf import settings
from agents.database.neo4j import Neo4jService
from agents.a2a_client import A2AClient, A2AAgentCard

logger = logging.getLogger(__name__)
conversation_logger = logging.getLogger('agents.conversation')
a2a_logger = logging.getLogger('agents.a2a_communication')

def safe_log_text(text: str) -> str:
    """Preserve all text including Korean characters without any filtering"""
    if not text:
        return text
    # Simply return the original text without any encoding conversion or filtering
    return text

class BaseWorkerAgent(ABC):
    """Base class for all worker agents"""

    def __init__(self, agent_slug: str, agent_config: Dict[str, Any]):
        self.agent_slug = agent_slug
        self.config = agent_config
        self.neo4j_service = Neo4jService()
        self.neo4j_service.connect()  # Ensure Neo4j is connected
        self._a2a_clients: Dict[str, A2AClient] = {}

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Agent display name"""
        pass

    @property
    @abstractmethod
    def agent_description(self) -> str:
        """Agent description"""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Agent capabilities"""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Agent system prompt"""
        pass

    async def process_request(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """Process request - main entry point for conversation coordinator"""
        return await self.chat(user_input, context_id, session_id, user_name)

    async def chat(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """Main chat method that all workers must implement"""
        conversation_start = datetime.now()

        try:
            # Log conversation start with detailed format
            conversation_logger.info(f"")
            conversation_logger.info(f"=" * 80)
            conversation_logger.info(f"SESSION: {session_id} | CONVERSATION START")
            conversation_logger.info(f"=" * 80)
            conversation_logger.info(f"Timestamp: {conversation_start.isoformat()}")
            conversation_logger.info(f"Agent: {self.agent_slug}")
            conversation_logger.info(f"User: {user_name}")
            conversation_logger.info(f"Context ID: {context_id}")
            conversation_logger.info(f"-" * 40)
            conversation_logger.info(f"USER: {safe_log_text(user_input)}")

            # Save user input to Neo4j
            await self._save_message_to_neo4j(
                context_id=context_id,
                session_id=session_id,
                message_type="user",
                content=user_input,
                user_name=user_name
            )

            # Generate response
            response = await self._generate_response(user_input, context_id, session_id, user_name)

            # Save agent response to Neo4j
            await self._save_message_to_neo4j(
                context_id=context_id,
                session_id=session_id,
                message_type="assistant",
                content=response,
                user_name=self.agent_slug
            )

            # Log conversation completion
            conversation_end = datetime.now()
            duration = (conversation_end - conversation_start).total_seconds()
            conversation_logger.info(f"-" * 40)
            conversation_logger.info(f"AGENT ({self.agent_slug}): {response}")
            conversation_logger.info(f"-" * 40)
            conversation_logger.info(f"Duration: {duration:.2f}s | Status: SUCCESS")
            conversation_logger.info(f"SESSION: {session_id} | CONVERSATION END")
            conversation_logger.info(f"=" * 80)
            conversation_logger.info(f"")

            return response

        except Exception as e:
            conversation_end = datetime.now()
            duration = (conversation_end - conversation_start).total_seconds()
            conversation_logger.error(f"-" * 40)
            conversation_logger.error(f"AGENT ({self.agent_slug}): ERROR - {str(e)}")
            conversation_logger.error(f"-" * 40)
            conversation_logger.error(f"Duration: {duration:.2f}s | Status: FAILED")
            conversation_logger.error(f"SESSION: {session_id} | CONVERSATION END")
            conversation_logger.error(f"=" * 80)
            conversation_logger.error(f"")
            logger.error(f"Error in {self.agent_slug} chat: {e}")
            return f"I apologize, but I encountered an error: {str(e)}"

    @abstractmethod
    async def _generate_response(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """Generate response - must be implemented by each worker"""
        pass

    async def _save_message_to_neo4j(self, context_id: str, session_id: str, message_type: str, content: str, user_name: str):
        """Save message to Neo4j graph database"""
        try:
            query = """
            MERGE (s:Session {session_id: $session_id})
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
            """

            self.neo4j_service.execute_query(
                query,
                {
                    'message_id': str(uuid4()),
                    'session_id': session_id,
                    'context_id': context_id,
                    'message_type': message_type,
                    'content': content,
                    'user_name': user_name,
                    'agent_slug': self.agent_slug,
                    'timestamp': datetime.now().isoformat()
                }
            )

        except Exception as e:
            logger.error(f"Error saving message to Neo4j: {e}")

    async def communicate_with_agent(self, target_agent_slug: str, message: str, context_id: str = None) -> Optional[str]:
        """Communicate with another worker agent via A2A protocol"""
        communication_id = str(uuid4())
        communication_start = datetime.now()

        # Log A2A communication start in official A2A protocol format
        a2a_start_log = {
            "jsonrpc": "2.0",
            "method": "agent.communication.start",
            "params": {
                "communication_id": communication_id,
                "timestamp": communication_start.isoformat(),
                "source_agent": {
                    "slug": self.agent_slug,
                    "name": self.agent_name
                },
                "target_agent": {
                    "slug": target_agent_slug
                },
                "message": {
                    "content": message,
                    "context_id": context_id or f"worker_to_worker_{self.agent_slug}_{target_agent_slug}",
                    "message_type": "text"
                }
            },
            "id": communication_id
        }
        a2a_logger.info(json.dumps(a2a_start_log, ensure_ascii=False, indent=2))

        try:
            # Get or create A2A client for target agent
            if target_agent_slug not in self._a2a_clients:
                # Discover target agent card
                from agents.a2a_client import A2ACardResolver
                resolver = A2ACardResolver(settings.A2A_BASE_URL)
                target_card = await resolver.get_agent_card(target_agent_slug)

                if not target_card:
                    logger.error(f"Could not discover agent card for {target_agent_slug}")

                    # Log A2A communication failure in A2A protocol format
                    a2a_error_log = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32001,
                            "message": "Agent discovery failed",
                            "data": {
                                "target_agent": target_agent_slug,
                                "error": f"Could not discover agent card for {target_agent_slug}",
                                "duration_ms": (datetime.now() - communication_start).total_seconds() * 1000,
                                "timestamp": datetime.now().isoformat()
                            }
                        },
                        "id": communication_id
                    }
                    a2a_logger.error(json.dumps(a2a_error_log, ensure_ascii=False, indent=2))
                    return None

                self._a2a_clients[target_agent_slug] = A2AClient(target_card)

            # Send message
            client = self._a2a_clients[target_agent_slug]
            response = await client.send_message(
                message=message,
                context_id=context_id or f"worker_to_worker_{self.agent_slug}_{target_agent_slug}",
                session_id=f"worker_session_{uuid4()}"
            )

            # Log successful A2A communication in A2A protocol format
            communication_end = datetime.now()
            duration_ms = (communication_end - communication_start).total_seconds() * 1000

            a2a_success_log = {
                "jsonrpc": "2.0",
                "result": {
                    "communication_id": communication_id,
                    "timestamp": communication_end.isoformat(),
                    "source_agent": {
                        "slug": self.agent_slug,
                        "name": self.agent_name
                    },
                    "target_agent": {
                        "slug": target_agent_slug
                    },
                    "response": {
                        "content": response,
                        "message_type": "text"
                    },
                    "performance": {
                        "duration_ms": duration_ms,
                        "status": "SUCCESS"
                    }
                },
                "id": communication_id
            }
            a2a_logger.info(json.dumps(a2a_success_log, ensure_ascii=False, indent=2))

            return response

        except Exception as e:
            # Log A2A communication error in A2A protocol format
            communication_end = datetime.now()
            duration_ms = (communication_end - communication_start).total_seconds() * 1000

            a2a_error_log = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32002,
                    "message": "Agent communication failed",
                    "data": {
                        "communication_id": communication_id,
                        "timestamp": communication_end.isoformat(),
                        "source_agent": self.agent_slug,
                        "target_agent": target_agent_slug,
                        "error": str(e),
                        "duration_ms": duration_ms,
                        "status": "FAILED"
                    }
                },
                "id": communication_id
            }
            a2a_logger.error(json.dumps(a2a_error_log, ensure_ascii=False, indent=2))

            logger.error(f"Error communicating with {target_agent_slug}: {e}")
            return None

    def generate_agent_card(self) -> Dict[str, Any]:
        """Generate A2A-compliant agent card"""
        return {
            "name": self.agent_name,
            "description": self.agent_description,
            "version": "1.0.0",
            "agent_type": "worker",
            "capabilities": self.capabilities,
            "protocols": ["a2a", "json-rpc-2.0"],
            "transport": ["http", "https"],
            "skills": [
                {
                    "name": "chat",
                    "description": "Chat and task assistance",
                    "type": "chat_completion",
                    "input_types": ["text"],
                    "output_types": ["text"]
                }
            ],
            "endpoints": {
                "chat": f"{settings.A2A_BASE_URL}/agents/{self.agent_slug}/chat/",
                "status": f"{settings.A2A_BASE_URL}/agents/{self.agent_slug}/status/",
                "a2a": f"{settings.A2A_BASE_URL}/agents/{self.agent_slug}/chat/",
                "jsonrpc": f"{settings.A2A_BASE_URL}/agents/{self.agent_slug}/chat/"
            },
            "authentication": {
                "type": "none",
                "description": "No authentication required for demo"
            },
            "rate_limits": {
                "requests_per_minute": self.config.get('rate_limit_per_minute', 30),
                "concurrent_sessions": self.config.get('max_concurrent_sessions', 5)
            },
            "metadata": {
                "framework": "langgraph",
                "worker_type": self.__class__.__name__,
                "created_at": datetime.now().isoformat()
            }
        }