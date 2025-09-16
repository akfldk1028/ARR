"""
Neo4j Conversation Tracker for A2A Integration
Automatically tracks and stores agent conversations in graph database
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4

from .neo4j_connection import Neo4jConnection
from models.graph_models import (
    UserNode, AgentNode, ConversationNode, MessageNode, 
    RelationshipType, Relationship
)

logger = logging.getLogger(__name__)

class ConversationTracker:
    """Tracks and stores A2A conversations in Neo4j graph"""
    
    def __init__(self, neo4j_connection: Neo4jConnection):
        self.db = neo4j_connection
        self.active_conversations: Dict[str, ConversationNode] = {}
        
    async def start_conversation(self, 
                               session_id: str, 
                               context_id: str, 
                               user_name: Optional[str] = None,
                               intent: Optional[str] = None) -> ConversationNode:
        """Start tracking a new conversation"""
        try:
            # Create or get user node
            user = await self.get_or_create_user(session_id, user_name)
            
            # Create conversation node
            conversation = ConversationNode(
                conversation_id=str(uuid4()),
                context_id=context_id,
                intent=intent,
                started_at=datetime.now()
            )
            
            # Store in database
            await self.create_conversation_in_db(conversation, user.id)
            
            # Track active conversation
            self.active_conversations[context_id] = conversation
            
            logger.info(f"🎬 Started conversation tracking: {conversation.conversation_id}")
            return conversation
            
        except Exception as e:
            logger.error(f"❌ Error starting conversation: {str(e)}")
            raise
    
    async def log_user_message(self, 
                             context_id: str, 
                             message_content: str, 
                             session_id: str) -> MessageNode:
        """Log a user message"""
        try:
            # Get or create conversation
            conversation = await self.get_or_create_conversation(context_id, session_id)
            
            # Create message node
            message = MessageNode(
                message_id=str(uuid4()),
                conversation_id=conversation.conversation_id,
                content=message_content,
                role="user",
                timestamp=datetime.now()
            )
            
            # Store in database
            await self.create_message_in_db(message, conversation.id, session_id)
            
            # Update conversation stats
            await self.update_conversation_stats(conversation.id)
            
            logger.info(f"👤 User message logged: {message.message_id[:8]}...")
            return message
            
        except Exception as e:
            logger.error(f"❌ Error logging user message: {str(e)}")
            raise
    
    async def log_agent_request(self, 
                              context_id: str,
                              from_agent: str,
                              to_agent: str,
                              request_content: str,
                              a2a_request_id: str) -> MessageNode:
        """Log an A2A agent request"""
        try:
            # Get conversation
            conversation = self.active_conversations.get(context_id)
            if not conversation:
                # Try to find in database
                conversation = await self.find_conversation_by_context(context_id)
                if not conversation:
                    logger.warning(f"No conversation found for context: {context_id}")
                    return None
            
            # Ensure agents exist in database
            await self.get_or_create_agent(from_agent, "unknown", "http://unknown")
            await self.get_or_create_agent(to_agent, "unknown", "http://unknown")
            
            # Create message node
            message = MessageNode(
                message_id=str(uuid4()),
                conversation_id=conversation.conversation_id,
                content=request_content,
                role="agent",
                message_type="a2a_request",
                a2a_request_id=a2a_request_id,
                timestamp=datetime.now()
            )
            
            # Store in database with agent relationship
            await self.create_agent_message_in_db(message, conversation.id, from_agent, to_agent)
            
            logger.info(f"🤖 Agent request logged: {from_agent} -> {to_agent}")
            return message
            
        except Exception as e:
            logger.error(f"❌ Error logging agent request: {str(e)}")
            raise
    
    async def log_agent_response(self, 
                               context_id: str,
                               from_agent: str,
                               to_agent: str,
                               response_content: str,
                               a2a_response_id: str,
                               request_message_id: Optional[str] = None,
                               response_time_ms: Optional[float] = None) -> MessageNode:
        """Log an A2A agent response"""
        try:
            # Get conversation
            conversation = self.active_conversations.get(context_id)
            if not conversation:
                conversation = await self.find_conversation_by_context(context_id)
                if not conversation:
                    logger.warning(f"No conversation found for context: {context_id}")
                    return None
            
            # Create message node
            message = MessageNode(
                message_id=str(uuid4()),
                conversation_id=conversation.conversation_id,
                content=response_content,
                role="agent",
                message_type="a2a_response",
                a2a_response_id=a2a_response_id,
                response_time_ms=response_time_ms,
                timestamp=datetime.now()
            )
            
            # Store in database with relationships
            await self.create_agent_message_in_db(message, conversation.id, from_agent, to_agent)
            
            # Link to request message if provided
            if request_message_id:
                await self.link_request_response(request_message_id, message.id)
            
            # Update agent performance metrics
            await self.update_agent_metrics(from_agent, response_time_ms, True)
            
            logger.info(f"📤 Agent response logged: {from_agent} -> {to_agent}")
            return message
            
        except Exception as e:
            logger.error(f"❌ Error logging agent response: {str(e)}")
            raise
    
    async def end_conversation(self, 
                             context_id: str, 
                             success: bool = True, 
                             user_satisfaction: Optional[int] = None) -> bool:
        """Mark conversation as ended"""
        try:
            conversation = self.active_conversations.get(context_id)
            if not conversation:
                logger.warning(f"No active conversation found for context: {context_id}")
                return False
            
            # Update conversation
            end_time = datetime.now()
            duration = (end_time - conversation.started_at).total_seconds()
            
            query = """
            MATCH (c:Conversation {id: $conversation_id})
            SET c.ended_at = datetime(),
                c.status = 'completed',
                c.duration_seconds = $duration,
                c.was_successful = $success,
                c.user_satisfaction = $satisfaction
            RETURN c
            """
            
            params = {
                "conversation_id": conversation.id,
                "duration": duration,
                "success": success,
                "satisfaction": user_satisfaction
            }
            
            await self.db.execute_write_query(query, params)
            
            # Remove from active conversations
            del self.active_conversations[context_id]
            
            logger.info(f"🏁 Conversation ended: {conversation.conversation_id} (success: {success})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error ending conversation: {str(e)}")
            return False
    
    # Helper methods
    
    async def get_or_create_user(self, session_id: str, name: Optional[str] = None) -> UserNode:
        """Get existing user or create new one"""
        # Check if user exists
        query = "MATCH (u:User {session_id: $session_id}) RETURN u"
        result = self.db.execute_query(query, {"session_id": session_id})
        
        if result:
            # User exists, return it
            user_data = result[0]["u"]
            # Convert Neo4j datetime to Python datetime
            if "created_at" in user_data and hasattr(user_data["created_at"], "to_native"):
                user_data["created_at"] = user_data["created_at"].to_native()
            if "updated_at" in user_data and hasattr(user_data["updated_at"], "to_native"):
                user_data["updated_at"] = user_data["updated_at"].to_native()
            if "last_active" in user_data and hasattr(user_data["last_active"], "to_native"):
                user_data["last_active"] = user_data["last_active"].to_native()
            return UserNode(**user_data)
        else:
            # Create new user
            user = UserNode(session_id=session_id, name=name)
            
            create_query = """
            CREATE (u:User {
                id: $id,
                session_id: $session_id,
                user_type: $user_type,
                name: $name,
                created_at: datetime(),
                total_conversations: 0,
                total_messages: 0
            })
            RETURN u
            """
            
            params = {
                "id": user.id,
                "session_id": session_id,
                "user_type": user.user_type,
                "name": name
            }
            
            self.db.execute_write_query(create_query, params)
            logger.info(f"👤 Created new user: {session_id}")
            return user
    
    async def get_or_create_agent(self, agent_name: str, agent_type: str, endpoint: str) -> AgentNode:
        """Get existing agent or create new one"""
        # Check if agent exists
        query = "MATCH (a:Agent {name: $agent_name}) RETURN a"
        result = self.db.execute_query(query, {"agent_name": agent_name})
        
        if result:
            agent_data = result[0]["a"]
            # Convert Neo4j datetime to Python datetime
            if "created_at" in agent_data and hasattr(agent_data["created_at"], "to_native"):
                agent_data["created_at"] = agent_data["created_at"].to_native()
            if "updated_at" in agent_data and hasattr(agent_data["updated_at"], "to_native"):
                agent_data["updated_at"] = agent_data["updated_at"].to_native()
            if "last_health_check" in agent_data and hasattr(agent_data["last_health_check"], "to_native"):
                agent_data["last_health_check"] = agent_data["last_health_check"].to_native()
            return AgentNode(**agent_data)
        else:
            # Create new agent
            agent = AgentNode(
                name=agent_name,
                agent_type=agent_type,
                endpoint=endpoint
            )
            
            create_query = """
            CREATE (a:Agent {
                id: $id,
                name: $name,
                agent_type: $agent_type,
                endpoint: $endpoint,
                description: $description,
                version: $version,
                created_at: datetime(),
                total_requests: 0,
                total_responses: 0,
                success_rate: 0.0,
                average_response_time: 0.0,
                is_active: true
            })
            RETURN a
            """
            
            params = agent.to_dict()
            self.db.execute_write_query(create_query, params)
            logger.info(f"🤖 Created new agent: {agent_name}")
            return agent
    
    async def create_conversation_in_db(self, conversation: ConversationNode, user_id: str):
        """Create conversation node and link to user"""
        create_query = """
        CREATE (c:Conversation {
            id: $id,
            conversation_id: $conversation_id,
            context_id: $context_id,
            status: $status,
            topic: $topic,
            intent: $intent,
            language: $language,
            message_count: 0,
            agent_count: 0,
            started_at: datetime(),
            was_successful: null
        })
        WITH c
        MATCH (u:User {id: $user_id})
        CREATE (u)-[:STARTS_CONVERSATION {timestamp: datetime()}]->(c)
        RETURN c
        """
        
        params = conversation.to_dict()
        params["user_id"] = user_id
        
        self.db.execute_write_query(create_query, params)
    
    async def create_message_in_db(self, message: MessageNode, conversation_id: str, sender_id: str):
        """Create message node and relationships"""
        create_query = """
        CREATE (m:Message {
            id: $id,
            message_id: $message_id,
            conversation_id: $conversation_id,
            content: $content,
            role: $role,
            message_type: $message_type,
            timestamp: datetime(),
            status: 'sent'
        })
        WITH m
        MATCH (c:Conversation {id: $conversation_id}), (sender {id: $sender_id})
        CREATE (c)-[:CONTAINS_MESSAGE]->(m),
               (sender)-[:SENDS_MESSAGE]->(m)
        RETURN m
        """
        
        params = message.to_dict()
        params["conversation_id"] = conversation_id
        params["sender_id"] = sender_id
        
        self.db.execute_write_query(create_query, params)
    
    async def create_agent_message_in_db(self, 
                                       message: MessageNode, 
                                       conversation_id: str, 
                                       from_agent: str, 
                                       to_agent: str):
        """Create agent message with proper relationships"""
        create_query = """
        CREATE (m:Message {
            id: $id,
            message_id: $message_id,
            conversation_id: $conversation_id,
            content: $content,
            role: $role,
            message_type: $message_type,
            a2a_request_id: $a2a_request_id,
            a2a_response_id: $a2a_response_id,
            response_time_ms: $response_time_ms,
            timestamp: datetime(),
            status: 'sent'
        })
        WITH m
        MATCH (c:Conversation {id: $conversation_id}),
              (from_a:Agent {name: $from_agent}),
              (to_a:Agent {name: $to_agent})
        CREATE (c)-[:CONTAINS_MESSAGE]->(m),
               (from_a)-[:SENDS_MESSAGE]->(m),
               (from_a)-[:DELEGATES_TO {timestamp: datetime(), message_id: $message_id}]->(to_a)
        RETURN m
        """
        
        params = message.to_dict()
        params["conversation_id"] = conversation_id
        params["from_agent"] = from_agent
        params["to_agent"] = to_agent
        
        self.db.execute_write_query(create_query, params)
    
    async def update_conversation_stats(self, conversation_id: str):
        """Update conversation message count"""
        query = """
        MATCH (c:Conversation {id: $conversation_id})
        OPTIONAL MATCH (c)-[:CONTAINS_MESSAGE]->(m:Message)
        WITH c, count(m) as msg_count
        SET c.message_count = msg_count
        RETURN c
        """
        
        self.db.execute_write_query(query, {"conversation_id": conversation_id})
    
    async def update_agent_metrics(self, agent_name: str, response_time_ms: Optional[float], success: bool):
        """Update agent performance metrics"""
        query = """
        MATCH (a:Agent {name: $agent_name})
        SET a.total_responses = a.total_responses + 1,
            a.last_health_check = datetime()
        """
        
        params = {"agent_name": agent_name}
        
        if response_time_ms:
            query += """
            SET a.average_response_time = 
                (a.average_response_time * (a.total_responses - 1) + $response_time_ms) / a.total_responses
            """
            params["response_time_ms"] = response_time_ms
        
        if success:
            query += """
            SET a.success_rate = 
                (a.success_rate * (a.total_responses - 1) + 1.0) / a.total_responses
            """
        
        query += " RETURN a"
        
        self.db.execute_write_query(query, params)
    
    async def get_or_create_conversation(self, context_id: str, session_id: str) -> ConversationNode:
        """Get existing conversation or create new one"""
        if context_id in self.active_conversations:
            return self.active_conversations[context_id]
        
        # Try to find existing conversation
        existing = await self.find_conversation_by_context(context_id)
        if existing:
            self.active_conversations[context_id] = existing
            return existing
        
        # Create new conversation
        return await self.start_conversation(session_id, context_id)
    
    async def find_conversation_by_context(self, context_id: str) -> Optional[ConversationNode]:
        """Find conversation by context ID"""
        query = "MATCH (c:Conversation {context_id: $context_id}) RETURN c"
        result = self.db.execute_query(query, {"context_id": context_id})
        
        if result:
            conv_data = result[0]["c"]
            # Convert Neo4j datetime to Python datetime
            if "created_at" in conv_data and hasattr(conv_data["created_at"], "to_native"):
                conv_data["created_at"] = conv_data["created_at"].to_native()
            if "updated_at" in conv_data and hasattr(conv_data["updated_at"], "to_native"):
                conv_data["updated_at"] = conv_data["updated_at"].to_native()
            if "started_at" in conv_data and hasattr(conv_data["started_at"], "to_native"):
                conv_data["started_at"] = conv_data["started_at"].to_native()
            if "ended_at" in conv_data and hasattr(conv_data["ended_at"], "to_native"):
                conv_data["ended_at"] = conv_data["ended_at"].to_native()
            return ConversationNode(**conv_data)
        return None
    
    async def link_request_response(self, request_message_id: str, response_message_id: str):
        """Link request and response messages"""
        query = """
        MATCH (req:Message {id: $request_id}), (resp:Message {id: $response_id})
        CREATE (resp)-[:REPLIES_TO {timestamp: datetime()}]->(req)
        """
        
        params = {
            "request_id": request_message_id,
            "response_id": response_message_id
        }
        
        self.db.execute_write_query(query, params)