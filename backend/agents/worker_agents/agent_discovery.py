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
        self._semantic_model = None
        self._categories = {}
        self._category_embeddings = {}

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
            # Allow hostagent (and legacy test-agent/general-worker) to delegate to specialists
            if current_agent_slug not in ['hostagent', 'test-agent', 'general-worker']:
                logger.info(f"Not delegating - current agent {current_agent_slug} is a specialist")
                return False, None

            # Semantic routing using sentence-transformers for intelligent delegation
            try:
                from sentence_transformers import SentenceTransformer
                from sklearn.metrics.pairwise import cosine_similarity
                import numpy as np

                # Initialize model and load categories from JSON cards (cache for reuse)
                if self._semantic_model is None:
                    logger.info("Loading semantic routing model and categories from JSON cards...")
                    # Use lightweight multilingual model for fast Korean support
                    self._semantic_model = SentenceTransformer('distiluse-base-multilingual-cased-v2')

                    # Load categories dynamically from agent card skills
                    await self._load_categories_from_cards()

                    # Pre-compute embeddings for categories
                    for category, examples in self._categories.items():
                        if examples:  # Only encode if we have examples
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

                # Decision thresholds - Dynamic based on skill categories
                # General chat skills should not trigger delegation
                general_skills = ['general_chat', 'greetings', 'semantic_routing']

                if best_category in general_skills and best_score > 0.8:
                    logger.info(f"General chat detected ({best_category}), no delegation needed")
                    return False, None
                elif best_category not in general_skills and best_score > 0.2:
                    logger.info(f"Specialized task detected: {best_category} (score: {best_score:.3f}), proceeding with delegation")
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
                # Map skill category to agent slug by checking which agent has this skill
                from agents.worker_agents.card_loader import AgentCardLoader
                cards = AgentCardLoader.load_all_cards()

                for agent_slug, card in cards.items():
                    for skill in card.get('skills', []):
                        if skill.get('id') == best_category:
                            selected_agent = agent_slug
                            logger.info(f"LLM failed, fallback to {selected_agent} based on skill match: {best_category}")
                            break
                    if selected_agent:
                        break

                # If still no match, no delegation
                if not selected_agent:
                    logger.info(f"LLM failed and no agent found for category {best_category}, no delegation")
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

    async def _load_categories_from_cards(self):
        """
        Load semantic routing categories from JSON agent card skills
        Replaces hardcoded categories with dynamic loading from source of truth
        """
        from agents.worker_agents.card_loader import AgentCardLoader

        try:
            # Load all agent cards
            cards = AgentCardLoader.load_all_cards()
            logger.info(f"Loading semantic categories from {len(cards)} agent cards")

            # Build categories from card skills
            for agent_slug, card in cards.items():
                skills = card.get('skills', [])

                for skill in skills:
                    skill_id = skill.get('id')
                    if not skill_id:
                        continue

                    # Initialize category if not exists
                    if skill_id not in self._categories:
                        self._categories[skill_id] = []

                    # Add tags as training examples
                    tags = skill.get('tags', [])
                    self._categories[skill_id].extend(tags)

                    # Add examples as training data
                    examples = skill.get('examples', [])
                    self._categories[skill_id].extend(examples)

                    logger.debug(f"Loaded skill '{skill_id}' from {agent_slug}: {len(tags)} tags, {len(examples)} examples")

            logger.info(f"Loaded {len(self._categories)} semantic categories from JSON cards")
            for category, examples in self._categories.items():
                logger.info(f"  - {category}: {len(examples)} training examples")

        except Exception as e:
            logger.error(f"Error loading categories from cards: {e}")
            # Fallback to minimal general category if loading fails
            self._categories = {
                'general_chat': ["hello", "hi", "안녕", "안녕하세요"]
            }