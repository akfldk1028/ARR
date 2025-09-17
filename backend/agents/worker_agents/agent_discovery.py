"""
A2A Agent Discovery Service
Implements proper agent discovery via agent cards for delegation
"""

import logging
from typing import Dict, List, Optional, Any
import json

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from ..a2a_client import A2ACardResolver

logger = logging.getLogger(__name__)

class AgentDiscoveryService:
    """Service for discovering and selecting appropriate agents for tasks"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self._agent_cards_cache: Dict[str, Dict] = {}

    async def discover_available_agents(self) -> Dict[str, Dict]:
        """Discover all available agents via their agent cards"""
        try:
            # Get agent cards from our own system
            resolver = A2ACardResolver("http://localhost:8000")

            # Get all agents list first
            all_agents_card = await resolver.get_agent_card()  # No slug = get all
            if not all_agents_card:
                logger.error("Failed to discover agent list")
                return {}

            # Parse agent list data
            if hasattr(all_agents_card, 'data') and 'agents' in all_agents_card.data:
                agents_list = all_agents_card.data['agents']
            else:
                logger.warning("No agents found in discovery")
                return {}

            # Get individual agent cards
            discovered_agents = {}
            for agent_info in agents_list:
                agent_slug = agent_info.get('slug')
                if agent_slug:
                    agent_card = await resolver.get_agent_card(agent_slug)
                    if agent_card:
                        discovered_agents[agent_slug] = agent_card.data
                        logger.info(f"Discovered agent: {agent_slug}")

            self._agent_cards_cache = discovered_agents
            return discovered_agents

        except Exception as e:
            logger.error(f"Error discovering agents: {e}")
            return {}

    async def select_best_agent_for_task(self, user_request: str, available_agents: Dict[str, Dict] = None) -> Optional[str]:
        """Use LLM to select the best agent for a given user request"""
        try:
            if not available_agents:
                available_agents = await self.discover_available_agents()

            if not available_agents:
                logger.warning("No agents available for selection")
                return None

            # Create agent capabilities summary for LLM
            agent_capabilities = {}
            for agent_slug, agent_card in available_agents.items():
                agent_capabilities[agent_slug] = {
                    'name': agent_card.get('name', agent_slug),
                    'description': agent_card.get('description', ''),
                    'capabilities': agent_card.get('capabilities', []),
                    'skills': [skill.get('description', skill.get('name', ''))
                              for skill in agent_card.get('skills', [])]
                }

            # Prepare LLM prompt for agent selection
            selection_prompt = f"""
            You are an AI agent coordinator. A user has made the following request:

            User Request: "{user_request}"

            Available Agents and their capabilities:
            {json.dumps(agent_capabilities, indent=2)}

            Your task is to select the MOST APPROPRIATE agent to handle this request.

            Rules:
            1. Analyze the user's request to understand what type of help they need
            2. Match the request with agent capabilities and skills
            3. If NO agent has specific expertise for this request, return "test-agent"
            4. If multiple agents could help, choose the most specialized one
            5. CRITICAL: ONLY return the agent slug (key) - NOTHING ELSE, NO EXPLANATION

            Return ONLY the agent slug (e.g., "flight-specialist" or "test-agent"):
            """

            messages = [
                SystemMessage(content="You are an expert at matching user requests to appropriate AI agents. Return ONLY the agent slug, nothing else."),
                HumanMessage(content=selection_prompt)
            ]

            response = await self.llm.ainvoke(messages)
            selected_agent = response.content.strip()

            # Validate the selection
            if selected_agent in available_agents:
                logger.info(f"Selected agent '{selected_agent}' for request: {user_request[:50]}...")
                return selected_agent
            else:
                logger.warning(f"LLM selected invalid agent '{selected_agent}', falling back to default")
                # Fallback to general agent or first available
                return 'test-agent' if 'test-agent' in available_agents else list(available_agents.keys())[0]

        except Exception as e:
            logger.error(f"Error selecting agent: {e}")
            return None

    async def should_delegate_request(self, user_request: str, current_agent_slug: str) -> tuple[bool, Optional[str]]:
        """
        Determine if request should be delegated to another agent
        Returns (should_delegate, target_agent_slug)
        """
        try:
            logger.info(f"AgentDiscoveryService: Checking delegation for '{user_request}' from {current_agent_slug}")

            # Don't delegate if we're already a specialist being consulted
            if current_agent_slug != 'test-agent':  # test-agent is our general coordinator
                logger.info(f"Not delegating - current agent {current_agent_slug} is not test-agent")
                return False, None

            available_agents = await self.discover_available_agents()
            logger.info(f"Discovered {len(available_agents)} agents: {list(available_agents.keys())}")

            if not available_agents or len(available_agents) <= 1:
                logger.info("Not enough agents available for delegation")
                return False, None

            selected_agent = await self.select_best_agent_for_task(user_request, available_agents)
            logger.info(f"LLM selected agent: {selected_agent}")

            # Delegate if a different (specialist) agent was selected
            if selected_agent and selected_agent != current_agent_slug:
                logger.info(f"Delegating from {current_agent_slug} to {selected_agent}")
                return True, selected_agent

            logger.info(f"No delegation needed - selected same agent or no selection")
            return False, None

        except Exception as e:
            logger.error(f"Error in delegation decision: {e}")
            return False, None

    def get_cached_agent_info(self, agent_slug: str) -> Optional[Dict]:
        """Get cached agent card information"""
        return self._agent_cards_cache.get(agent_slug)