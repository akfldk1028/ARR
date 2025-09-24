"""
General Worker Agent - 범용 어시스턴트 에이전트
"""

import os
import asyncio
import logging
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver

from ..base import BaseWorkerAgent
from ..agent_discovery import AgentDiscoveryService

logger = logging.getLogger(__name__)

class GeneralWorkerAgent(BaseWorkerAgent):
    """General-purpose worker agent for diverse tasks"""

    def __init__(self, agent_slug: str, agent_config: Dict[str, Any]):
        super().__init__(agent_slug, agent_config)

        # Initialize OpenAI LLM
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.llm = ChatOpenAI(
            model=agent_config.get('model_name', 'gpt-3.5-turbo'),
            api_key=api_key,
            temperature=agent_config.get('config', {}).get('temperature', 0.7),
            max_tokens=agent_config.get('config', {}).get('max_tokens', 2048)
        )

        # Initialize A2A agent discovery service (with caching)
        self.discovery_service = AgentDiscoveryService(self.llm)
        self._agent_cache_timeout = 300  # 5분 캐시
        self._last_discovery_time = 0

    @property
    def agent_name(self) -> str:
        return self.config.get('name', 'General Assistant Agent')

    @property
    def agent_description(self) -> str:
        return self.config.get('description', 'General-purpose AI assistant for various tasks and questions')

    @property
    def capabilities(self) -> List[str]:
        return self.config.get('capabilities', ['text', 'conversation', 'general_assistance', 'worker_coordination'])

    @property
    def system_prompt(self) -> str:
        return self.config.get('system_prompt', '''You are a general-purpose AI assistant. You can:

1. Answer general questions and provide information
2. Help with various tasks and problem-solving
3. Coordinate with other specialized worker agents when needed
4. Provide explanations and tutorials on diverse topics

When a user asks about something that requires specialized knowledge (like flight booking, hotel reservations, etc.), you should offer to connect them with a relevant specialist agent.

Always be helpful, clear, and concise in your responses.''')

    async def _generate_response(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """Generate response using OpenAI LLM with proper A2A agent discovery"""
        import time
        start_time = time.time()

        try:
            # Use A2A agent discovery to determine if delegation is needed
            logger.info(f"General worker processing request: {user_input}")

            # Use LLM-based agent discovery for all requests
            if self.discovery_service:
                discovery_start = time.time()
                should_delegate, target_agent = await self.discovery_service.should_delegate_request(
                    user_request=user_input,
                    current_agent_slug=self.agent_slug
                )
                discovery_time = time.time() - discovery_start
                logger.info(f"LLM delegation decision: should_delegate={should_delegate}, target_agent={target_agent} (took {discovery_time:.2f}s)")
            else:
                # Fallback: no delegation without discovery service
                should_delegate = False
                target_agent = None
                logger.info("No discovery service available, handling request directly")

            if should_delegate and target_agent:
                # Get agent info for better announcement
                agent_info = None
                if self.discovery_service and hasattr(self.discovery_service, 'get_cached_agent_info'):
                    try:
                        agent_info = self.discovery_service.get_cached_agent_info(target_agent)
                    except Exception as e:
                        logger.warning(f"Could not get cached agent info: {e}")

                agent_name = agent_info.get('name', target_agent.replace('-', ' ')) if agent_info else target_agent.replace('-', ' ')

                # Announce delegation before proceeding
                delegation_announcement = f"I'll ask our {agent_name} specialist to help with your request. Please wait while I connect you..."

                # Try to communicate with the selected specialist agent with timeout
                try:
                    specialist_response = await asyncio.wait_for(
                        self.communicate_with_agent(
                            target_agent_slug=target_agent,
                            message=f"A user is asking: {user_input}",
                            context_id=context_id
                        ),
                        timeout=45.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout communicating with {target_agent}, falling back to general response")
                    specialist_response = None

                if specialist_response:
                    # Get agent info for better coordination
                    agent_info = None
                    if self.discovery_service and hasattr(self.discovery_service, 'get_cached_agent_info'):
                        try:
                            agent_info = self.discovery_service.get_cached_agent_info(target_agent)
                        except Exception as e:
                            logger.warning(f"Could not get cached agent info: {e}")
                    agent_name = agent_info.get('name', target_agent.replace('-', ' ')) if agent_info else target_agent.replace('-', ' ')

                    # Use LLM to generate coordinated response
                    coordination_context = f"""
                    I have consulted with our {agent_name} specialist about the user's request: "{user_input}"

                    The specialist provided this response: {specialist_response}

                    I need to provide a coordinated response that:
                    1. Acknowledges that I consulted with the specialist
                    2. Presents the specialist's response clearly to the user
                    3. Offers to help with any follow-up questions
                    4. Maintains a natural conversation flow

                    The user should see both my coordination and the specialist's detailed response.
                    """

                    coordination_messages = [
                        SystemMessage(content=self.system_prompt),
                        HumanMessage(content=coordination_context)
                    ]

                    try:
                        llm_start = time.time()
                        coordination_response = await self.llm.ainvoke(coordination_messages)
                        llm_time = time.time() - llm_start
                        total_time = time.time() - start_time
                        logger.info(f"Coordination LLM took {llm_time:.2f}s, total request: {total_time:.2f}s")
                        # Add a marker for UI to detect delegation with specialist response and include announcement
                        return f"[DELEGATION_ANNOUNCEMENT:{delegation_announcement}][DELEGATION_OCCURRED:{target_agent}][SPECIALIST_RESPONSE:{specialist_response}] {coordination_response.content}"
                    except Exception as e:
                        logger.error(f"Error in coordination response: {e}")
                        # Fallback to simple forwarding
                        return f"I've consulted with our {agent_name} for this request:\n\n{specialist_response}"
                else:
                    # No specialist response - provide general helpful fallback
                    return "안녕하세요! 무엇을 도와드릴까요? 궁금한 것이 있으시면 언제든 말씀해 주세요."

            # Regular conversation flow
            messages = [SystemMessage(content=self.system_prompt)]

            # Load recent conversation history from Neo4j
            try:
                history_query = """
                MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
                WHERE m.agent_slug = $agent_slug OR m.type = 'user'
                RETURN m.content as content, m.type as role, m.timestamp as timestamp
                ORDER BY m.timestamp DESC
                LIMIT 8
                """

                history = self.neo4j_service.execute_query(
                    history_query,
                    {
                        'session_id': session_id,
                        'agent_slug': self.agent_slug
                    }
                )

                # Add history to messages (reverse to get chronological order)
                for msg in reversed(history):
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        messages.append(AIMessage(content=msg["content"]))

            except Exception as e:
                logger.warning(f"Could not load conversation history: {e}")

            # Add current user message
            messages.append(HumanMessage(content=user_input))

            # Generate response
            llm_start = time.time()
            response = await self.llm.ainvoke(messages)
            llm_time = time.time() - llm_start
            total_time = time.time() - start_time
            logger.info(f"Regular LLM took {llm_time:.2f}s, total request: {total_time:.2f}s")
            return response.content

        except Exception as e:
            logger.error(f"Error generating response in GeneralWorkerAgent: {e}")
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"