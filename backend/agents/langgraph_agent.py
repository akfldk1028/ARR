"""
LangGraph Agent Implementation for Django - DEPRECATED

⚠️ This module is deprecated. Please use the new worker_agents structure:

from agents.worker_agents import get_worker_for_slug

The new structure provides:
- Clean separation of concerns
- Better organization and maintainability
- Enhanced A2A protocol support
- Improved worker-to-worker communication

This file is maintained for backward compatibility only.
"""

import warnings
warnings.warn(
    "langgraph_agent.py is deprecated. Use agents.worker_agents instead.",
    DeprecationWarning,
    stacklevel=2
)

import asyncio
import logging
import os
from typing import Dict, Any, Optional, TypedDict, List
from datetime import datetime

from langgraph.graph import StateGraph, MessagesState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from .services import neo4j_service

logger = logging.getLogger(__name__)

class AgentState(MessagesState):
    """State for our LangGraph agent"""
    user_input: str
    context_id: str
    session_id: str
    user_name: Optional[str] = None
    conversation_history: List[Dict] = []
    agent_response: str = ""

class LangGraphAgent:
    """LangGraph-based agent implementation"""

    def __init__(self, agent_config: Dict[str, Any]):
        self.agent_config = agent_config
        self.name = agent_config.get('name', 'LangGraph Agent')
        self.model_name = agent_config.get('model_name', 'gpt-3.5-turbo')
        self.system_prompt = agent_config.get('system_prompt', 'You are a helpful AI assistant.')

        # Initialize OpenAI LLM
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.llm = ChatOpenAI(
            model=self.model_name,
            api_key=api_key,
            temperature=agent_config.get('config', {}).get('temperature', 0.7),
            max_tokens=agent_config.get('config', {}).get('max_tokens', 2048)
        )

        # Create memory saver for persistence
        self.memory = MemorySaver()

        # Build the graph
        self.graph = self._build_graph()

        logger.info(f"LangGraph Agent '{self.name}' initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""

        # Define the graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("process_input", self._process_input)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("save_to_neo4j", self._save_to_neo4j)

        # Define edges
        workflow.set_entry_point("process_input")
        workflow.add_edge("process_input", "generate_response")
        workflow.add_edge("generate_response", "save_to_neo4j")
        workflow.set_finish_point("save_to_neo4j")

        return workflow.compile(checkpointer=self.memory)

    async def _process_input(self, state: AgentState) -> AgentState:
        """Process user input and prepare context"""
        user_input = state["user_input"]
        context_id = state["context_id"]
        session_id = state["session_id"]

        logger.info(f"Processing input for session {session_id}: {user_input[:50]}...")

        # Load conversation history from Neo4j if available
        if neo4j_service._driver:
            try:
                history_query = """
                MATCH (c:Conversation {conversation_id: $context_id})-[:HAS_MESSAGE]->(m:Message)
                RETURN m.content as content, m.role as role, m.timestamp as timestamp
                ORDER BY m.timestamp
                LIMIT 10
                """
                history = neo4j_service.execute_query(
                    history_query,
                    {"context_id": context_id}
                )
                state["conversation_history"] = history
                logger.info(f"Loaded {len(history)} previous messages")
            except Exception as e:
                logger.warning(f"Could not load history from Neo4j: {e}")
                state["conversation_history"] = []

        return state

    async def _generate_response(self, state: AgentState) -> AgentState:
        """Generate AI response using LLM"""
        user_input = state["user_input"]
        conversation_history = state.get("conversation_history", [])

        # Build message history
        messages = [SystemMessage(content=self.system_prompt)]

        # Add conversation history
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # Add current user message
        messages.append(HumanMessage(content=user_input))

        try:
            # Generate response
            response = await self.llm.ainvoke(messages)
            agent_response = response.content

            state["agent_response"] = agent_response
            state["messages"] = messages + [AIMessage(content=agent_response)]

            logger.info(f"Generated response: {agent_response[:100]}...")

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            state["agent_response"] = f"Sorry, I encountered an error: {str(e)}"

        return state

    async def _save_to_neo4j(self, state: AgentState) -> AgentState:
        """Save conversation to Neo4j"""
        if not neo4j_service._driver:
            logger.warning("Neo4j not available, skipping save")
            return state

        try:
            context_id = state["context_id"]
            session_id = state["session_id"]
            user_name = state.get("user_name", "anonymous")
            user_input = state["user_input"]
            agent_response = state["agent_response"]
            timestamp = datetime.now().isoformat()

            # Create or update conversation
            conversation_query = """
            MERGE (c:Conversation {conversation_id: $context_id})
            SET c.session_id = $session_id,
                c.last_updated = $timestamp,
                c.message_count = c.message_count + 2
            RETURN c
            """
            neo4j_service.execute_write_query(conversation_query, {
                "context_id": context_id,
                "session_id": session_id,
                "timestamp": timestamp
            })

            # Create user message
            user_message_query = """
            MATCH (c:Conversation {conversation_id: $context_id})
            CREATE (m:Message {
                content: $content,
                role: 'user',
                timestamp: $timestamp,
                session_id: $session_id
            })
            CREATE (c)-[:HAS_MESSAGE]->(m)
            RETURN m
            """
            neo4j_service.execute_write_query(user_message_query, {
                "context_id": context_id,
                "content": user_input,
                "timestamp": timestamp,
                "session_id": session_id
            })

            # Create assistant message
            assistant_message_query = """
            MATCH (c:Conversation {conversation_id: $context_id})
            CREATE (m:Message {
                content: $content,
                role: 'assistant',
                timestamp: $timestamp,
                session_id: $session_id
            })
            CREATE (c)-[:HAS_MESSAGE]->(m)
            RETURN m
            """
            neo4j_service.execute_write_query(assistant_message_query, {
                "context_id": context_id,
                "content": agent_response,
                "timestamp": timestamp,
                "session_id": session_id
            })

            logger.info(f"Saved conversation to Neo4j: {context_id}")

        except Exception as e:
            logger.error(f"Error saving to Neo4j: {e}")

        return state

    async def chat(
        self,
        user_input: str,
        context_id: str = "default",
        session_id: str = "default_session",
        user_name: str = None
    ) -> str:
        """Main chat interface"""

        if not user_input or not user_input.strip():
            return "Please provide a valid message."

        # Prepare initial state
        initial_state = AgentState(
            messages=[],
            user_input=user_input.strip(),
            context_id=context_id,
            session_id=session_id,
            user_name=user_name,
            conversation_history=[],
            agent_response=""
        )

        try:
            # Run the graph
            config = {"configurable": {"thread_id": context_id}}
            final_state = await self.graph.ainvoke(initial_state, config)

            return final_state["agent_response"]

        except Exception as e:
            logger.error(f"Error in chat method: {e}")
            return f"I apologize, but I encountered an error: {str(e)}"

class LangGraphAgentFactory:
    """Factory for creating LangGraph agents from Django models"""

    @staticmethod
    def create_agent_from_model(agent_model) -> LangGraphAgent:
        """Create LangGraph agent from Django Agent model"""

        agent_config = {
            'name': agent_model.name,
            'model_name': agent_model.model_name,
            'system_prompt': agent_model.system_prompt,
            'capabilities': agent_model.capabilities,
            'config': agent_model.config or {}
        }

        return LangGraphAgent(agent_config)

# Global agent instances cache
_agent_cache: Dict[str, LangGraphAgent] = {}

async def get_agent_for_slug(agent_slug: str) -> Optional[LangGraphAgent]:
    """Get or create LangGraph agent for given slug"""

    if agent_slug in _agent_cache:
        return _agent_cache[agent_slug]

    try:
        from django.core.asgi import get_asgi_application
        from asgiref.sync import sync_to_async
        from .models import Agent

        # Use sync_to_async for Django ORM operations
        get_agent = sync_to_async(Agent.objects.get)
        agent_model = await get_agent(slug=agent_slug, status='active')

        langgraph_agent = LangGraphAgentFactory.create_agent_from_model(agent_model)
        _agent_cache[agent_slug] = langgraph_agent

        logger.info(f"Created new LangGraph agent for slug: {agent_slug}")
        return langgraph_agent

    except Exception as e:
        logger.error(f"Error creating agent for slug {agent_slug}: {e}")
        return None