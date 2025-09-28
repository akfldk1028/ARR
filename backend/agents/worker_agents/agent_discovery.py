"""
A2A Agent Discovery Service
Implements proper agent discovery via agent cards for delegation
"""

import logging
from typing import Dict, List, Optional, Any
import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from django.conf import settings

from ..a2a_client import A2ACardResolver

logger = logging.getLogger(__name__)

def safe_log_text(text: str) -> str:
    """Preserve all text including Korean characters without any filtering"""
    if not text:
        return text
    # Simply return the original text without any encoding conversion or filtering
    return text

class AgentDiscoveryService:
    """Service for discovering and selecting appropriate agents for tasks"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self._agent_cards_cache: Dict[str, Dict] = {}

    async def discover_available_agents(self) -> Dict[str, Dict]:
        """Discover all available agents via their agent cards"""
        try:
            # Get agent cards from our own system
            resolver = A2ACardResolver(settings.A2A_BASE_URL)

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
            logger.info(f"AgentDiscoveryService: Checking delegation for '{safe_log_text(user_request)}' from {current_agent_slug}")

            # Don't delegate if we're already a specialist being consulted
            # Allow both test-agent and general-worker to delegate to specialists
            if current_agent_slug not in ['test-agent', 'general-worker']:
                logger.info(f"Not delegating - current agent {current_agent_slug} is a specialist")
                return False, None

            # Semantic routing using sentence-transformers for intelligent delegation
            try:
                from sentence_transformers import SentenceTransformer
                from sklearn.metrics.pairwise import cosine_similarity
                import numpy as np

                # Initialize model (cache for reuse)
                if not hasattr(self, '_semantic_model'):
                    logger.info("Loading semantic routing model...")
                    self._semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

                    # Define semantic categories with examples
                    self._categories = {
                        'greetings': [
                            "안녕하세요", "hello", "hi there", "good morning",
                            "안녕", "반갑습니다", "어떻게 지내세요", "뭐하고 계세요"
                        ],
                        'flight_booking': [
                            "비행기 예약해주세요", "항공편 알아봐주세요", "비행기표 예약",
                            "book a flight", "flight reservation", "airline tickets",
                            "항공료 확인", "비행 스케줄", "항공권 예약"
                        ],
                        'hotel_booking': [
                            "호텔 예약", "숙박 예약", "accommodation booking",
                            "hotel reservation", "숙소 찾아주세요", "room booking"
                        ]
                    }

                    # Pre-compute embeddings for categories
                    self._category_embeddings = {}
                    for category, examples in self._categories.items():
                        embeddings = self._semantic_model.encode(examples)
                        self._category_embeddings[category] = np.mean(embeddings, axis=0)

                # Encode user request
                user_embedding = self._semantic_model.encode([user_request])

                # Calculate similarities with each category
                similarities = {}
                for category, category_embedding in self._category_embeddings.items():
                    similarity = cosine_similarity(user_embedding, [category_embedding])[0][0]
                    similarities[category] = similarity

                # Find best match
                best_category = max(similarities, key=similarities.get)
                best_score = similarities[best_category]

                logger.info(f"Semantic routing: '{safe_log_text(user_request[:50])}...' → {best_category} (score: {best_score:.3f})")

                # Decision thresholds - 비행기 예약 우선순위 높임
                if best_category == 'greetings' and best_score > 0.8:
                    logger.info(f"Greeting detected via semantic similarity, no delegation needed")
                    return False, None
                elif best_category in ['flight_booking', 'hotel_booking'] and best_score > 0.2:
                    logger.info(f"Specialized task detected: {best_category}, proceeding with delegation")
                    # Continue to agent selection logic
                else:
                    logger.info(f"Low confidence or general conversation, no delegation needed")
                    return False, None

            except Exception as e:
                logger.error(f"Error in semantic routing: {e}")
                # Fallback to simple length check
                if len(user_request.strip()) <= 5:
                    return False, None

            available_agents = await self.discover_available_agents()
            logger.info(f"Discovered {len(available_agents)} agents: {list(available_agents.keys())}")

            if not available_agents or len(available_agents) <= 1:
                logger.info("Not enough agents available for delegation")
                return False, None

            selected_agent = await self.select_best_agent_for_task(user_request, available_agents)
            logger.info(f"LLM selected agent: {selected_agent}")

            # If LLM failed to select, fallback based on detected category
            if not selected_agent:
                # Get the detected category from semantic routing
                if best_category == 'flight_booking':
                    if 'flight-specialist' in available_agents:
                        selected_agent = 'flight-specialist'
                        logger.info(f"LLM failed, fallback to flight-specialist for flight_booking")
                    else:
                        selected_agent = 'general-worker' if 'general-worker' in available_agents else 'test-agent'
                elif best_category == 'hotel_booking':
                    # For hotel booking, use general-worker or test-agent as fallback
                    selected_agent = 'general-worker' if 'general-worker' in available_agents else 'test-agent'
                    logger.info(f"LLM failed, fallback to {selected_agent} for hotel_booking")
                else:
                    logger.info(f"LLM failed and no specific category, no delegation")
                    return False, None

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