"""
Neo4j Enhanced A2A Agent
Integrates existing A2A agents with Neo4j graph tracking
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4
import httpx

from semantic_kernel.agents.chat_completion.chat_completion_agent import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions.kernel_function_decorator import kernel_function

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from graph.neo4j_connection import Neo4jConnection
from graph.conversation_tracker import ConversationTracker

logger = logging.getLogger(__name__)

class Neo4jEnhancedFlightTool:
    """Flight booking tool enhanced with Neo4j conversation tracking"""
    
    def __init__(self, tracker: ConversationTracker, base_url: str):
        self.tracker = tracker
        self.base_url = base_url
    
    @kernel_function(
        description="Book a flight using the flight booking agent with graph tracking",
        name="book_flight_with_tracking"
    )
    async def book_flight(self, user_input: str) -> str:
        communication_id = str(uuid4())
        start_time = time.time()
        
        logger.info(f"🚀 Enhanced A2A request started: {communication_id}")
        
        # Get current conversation context from thread-local or global state
        # For now, we'll use a default context - in production, this would come from the conversation
        context_id = getattr(self, 'current_context_id', 'default_context')
        
        try:
            async with httpx.AsyncClient() as httpx_client:
                # Step 1: Resolve agent card
                resolver = A2ACardResolver(httpx_client=httpx_client, base_url=self.base_url)
                agent_card = await resolver.get_agent_card()
                
                # Step 2: Log agent request in Neo4j
                await self.tracker.log_agent_request(
                    context_id=context_id,
                    from_agent="TravelPlanningAgent",
                    to_agent="FlightBookingAgent", 
                    request_content=user_input,
                    a2a_request_id=communication_id
                )
                
                # Step 3: Make A2A call
                client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)
                
                request = SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(
                        message={
                            "messageId": uuid4().hex,
                            "role": "user",
                            "parts": [{"text": user_input}],
                            "contextId": context_id,
                        }
                    )
                )
                
                # Time the response
                response_start = time.time()
                response = await client.send_message(request)
                response_time_ms = (time.time() - response_start) * 1000
                
                result = response.model_dump(mode='json', exclude_none=True)
                
                # Step 4: Log agent response in Neo4j
                if "result" in result and "parts" in result["result"]:
                    response_text = result["result"]["parts"][0]["text"]
                    
                    await self.tracker.log_agent_response(
                        context_id=context_id,
                        from_agent="FlightBookingAgent",
                        to_agent="TravelPlanningAgent",
                        response_content=response_text,
                        a2a_response_id=result.get("id", communication_id),
                        response_time_ms=response_time_ms
                    )
                    
                    logger.info(f"✅ Enhanced A2A request completed: {communication_id}")
                    return response_text
                    
                elif "error" in result:
                    error_msg = f"Error from Flight Booking Agent: {result['error']}"
                    
                    await self.tracker.log_agent_response(
                        context_id=context_id,
                        from_agent="FlightBookingAgent",
                        to_agent="TravelPlanningAgent",
                        response_content=error_msg,
                        a2a_response_id=result.get("id", communication_id),
                        response_time_ms=response_time_ms
                    )
                    
                    logger.error(f"❌ A2A request failed: {error_msg}")
                    return error_msg
                    
                else:
                    error_msg = f"Unexpected response format from Flight Booking Agent"
                    logger.error(f"❌ Unexpected response: {result}")
                    return error_msg
                    
        except Exception as e:
            error_msg = f"Error communicating with Flight Booking Agent: {str(e)}"
            logger.error(f"❌ A2A request exception: {error_msg}")
            
            # Log the error in Neo4j too
            try:
                await self.tracker.log_agent_response(
                    context_id=context_id,
                    from_agent="FlightBookingAgent",
                    to_agent="TravelPlanningAgent",
                    response_content=error_msg,
                    a2a_response_id=communication_id,
                    response_time_ms=(time.time() - start_time) * 1000
                )
            except:
                pass  # Don't fail the main operation due to logging issues
                
            return error_msg

class Neo4jEnhancedTravelAgent:
    """Travel Agent enhanced with Neo4j conversation tracking"""
    
    def __init__(self, 
                 openai_api_key: str,
                 neo4j_connection: Neo4jConnection,
                 flight_agent_url: str = "http://localhost:9999"):
        
        self.neo4j_db = neo4j_connection
        self.tracker = ConversationTracker(neo4j_connection)
        
        # Initialize Semantic Kernel agent
        self.flight_tool = Neo4jEnhancedFlightTool(self.tracker, flight_agent_url)
        
        self.travel_agent = ChatCompletionAgent(
            service=OpenAIChatCompletion(
                api_key=openai_api_key,
                ai_model_id="gpt-3.5-turbo",
            ),
            name="Neo4jEnhancedTravelPlanner",
            instructions="""You are an enhanced travel planning assistant with conversation tracking capabilities.
            
Your role is to:
1. Understand customer travel needs
2. Use the flight booking tool to communicate with specialized agents
3. Provide comprehensive travel assistance
4. All your conversations are being tracked in a knowledge graph for continuous improvement

When customers ask about flights, use the book_flight_with_tracking tool to get information from our specialized flight booking agent.
Be conversational, helpful, and provide detailed responses based on the information you receive.""",
            plugins=[self.flight_tool]
        )
        
        # Chat history storage
        self.chat_history_store: Dict[str, ChatHistory] = {}
        
        logger.info("🎭 Neo4j Enhanced Travel Agent initialized")
    
    async def chat(self, 
                  user_input: str, 
                  context_id: str = "default",
                  session_id: str = "default_session",
                  user_name: Optional[str] = None) -> str:
        """Enhanced chat method with full Neo4j tracking"""
        
        try:
            # Step 1: Start or continue conversation tracking
            await self._ensure_conversation_tracking(context_id, session_id, user_name, user_input)
            
            # Step 2: Log user message
            await self.tracker.log_user_message(context_id, user_input, session_id)
            
            # Step 3: Set current context for tools
            self.flight_tool.current_context_id = context_id
            
            # Step 4: Get or create chat history
            chat_history = await self._get_or_create_chat_history(context_id)
            
            # Step 5: Add user message to chat history
            chat_history.messages.append(ChatMessageContent(role="user", content=user_input))
            
            # Step 6: Create thread and get response
            thread = ChatHistoryAgentThread(chat_history=chat_history, thread_id=str(uuid4()))
            response = await self.travel_agent.get_response(message=user_input, thread=thread)
            
            # Step 7: Add assistant response to chat history
            chat_history.messages.append(ChatMessageContent(role="assistant", content=response.content.content))
            
            # Step 8: Log assistant response (this represents the final response to user)
            # We could create a separate message type for final responses
            
            logger.info(f"💬 Enhanced chat completed for context: {context_id}")
            
            return response.content.content
            
        except Exception as e:
            logger.error(f"❌ Enhanced chat error: {str(e)}")
            error_response = f"I apologize, but I encountered an error while processing your request: {str(e)}"
            
            # Log error response
            try:
                await self.tracker.log_user_message(context_id, error_response, "system")
            except:
                pass
                
            return error_response
    
    async def end_conversation(self, 
                             context_id: str, 
                             success: bool = True, 
                             satisfaction: Optional[int] = None):
        """Properly end conversation tracking"""
        return await self.tracker.end_conversation(context_id, success, satisfaction)
    
    async def get_conversation_analytics(self, context_id: Optional[str] = None) -> Dict[str, Any]:
        """Get analytics for conversations"""
        if context_id:
            # Analytics for specific conversation
            query = """
            MATCH (c:Conversation {context_id: $context_id})
            OPTIONAL MATCH (c)-[:CONTAINS_MESSAGE]->(m:Message)
            OPTIONAL MATCH (c)-[:INVOLVES_AGENT]->(a:Agent)
            RETURN c, count(DISTINCT m) as message_count, collect(DISTINCT a.name) as agents
            """
            params = {"context_id": context_id}
        else:
            # Overall analytics
            query = """
            MATCH (c:Conversation)
            OPTIONAL MATCH (c)-[:CONTAINS_MESSAGE]->(m:Message)
            RETURN count(DISTINCT c) as total_conversations,
                   count(m) as total_messages,
                   avg(c.duration_seconds) as avg_duration,
                   avg(c.message_count) as avg_messages_per_conversation
            """
            params = {}
        
        result = self.neo4j_db.execute_query(query, params)
        return result[0] if result else {}
    
    async def get_agent_performance(self) -> List[Dict[str, Any]]:
        """Get performance metrics for all agents"""
        query = """
        MATCH (a:Agent)
        RETURN a.name as agent_name,
               a.agent_type as agent_type,
               a.total_requests as total_requests,
               a.total_responses as total_responses,
               a.success_rate as success_rate,
               a.average_response_time as avg_response_time_ms,
               a.is_active as is_active,
               a.last_health_check as last_check
        ORDER BY a.total_requests DESC
        """
        
        return self.neo4j_db.execute_query(query)
    
    async def get_popular_intents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most popular user intents"""
        query = """
        MATCH (c:Conversation)
        WHERE c.intent IS NOT NULL
        RETURN c.intent as intent, count(*) as frequency
        ORDER BY frequency DESC
        LIMIT $limit
        """
        
        return self.neo4j_db.execute_query(query, {"limit": limit})
    
    # Helper methods
    
    async def _ensure_conversation_tracking(self, 
                                          context_id: str, 
                                          session_id: str, 
                                          user_name: Optional[str],
                                          user_input: str):
        """Ensure conversation is being tracked"""
        if context_id not in self.tracker.active_conversations:
            # Try to determine intent from user input
            intent = await self._detect_intent(user_input)
            
            await self.tracker.start_conversation(
                session_id=session_id,
                context_id=context_id,
                user_name=user_name,
                intent=intent
            )
    
    async def _get_or_create_chat_history(self, context_id: str) -> ChatHistory:
        """Get or create chat history for context"""
        if context_id not in self.chat_history_store:
            self.chat_history_store[context_id] = ChatHistory(
                messages=[],
                system_message="You are an enhanced travel planning assistant with graph-based conversation tracking."
            )
        
        return self.chat_history_store[context_id]
    
    async def _detect_intent(self, user_input: str) -> Optional[str]:
        """Simple intent detection - could be enhanced with ML"""
        user_input_lower = user_input.lower()
        
        if any(word in user_input_lower for word in ['flight', 'fly', 'book', 'ticket', 'airline']):
            return 'flight_booking'
        elif any(word in user_input_lower for word in ['hotel', 'accommodation', 'stay', 'room']):
            return 'hotel_booking'
        elif any(word in user_input_lower for word in ['trip', 'travel', 'vacation', 'plan']):
            return 'trip_planning'
        else:
            return 'general_inquiry'