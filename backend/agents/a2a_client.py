"""
A2A (Agent-to-Agent) Client Implementation
Django-compatible A2A protocol client for worker agent communication
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

class A2AAgentCard:
    """A2A Agent Card representation"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @property
    def name(self) -> str:
        return self.data.get('name', 'Unknown Agent')

    @property
    def description(self) -> str:
        return self.data.get('description', '')

    @property
    def version(self) -> str:
        return self.data.get('version', '1.0.0')

    @property
    def capabilities(self) -> List[str]:
        return self.data.get('capabilities', [])

    @property
    def endpoints(self) -> Dict[str, str]:
        return self.data.get('endpoints', {})

class A2ACardResolver:
    """A2A Agent Card Discovery"""

    def __init__(self, base_url: str, httpx_client: Optional[httpx.AsyncClient] = None):
        self.base_url = base_url.rstrip('/')
        self.httpx_client = httpx_client
        self._own_client = httpx_client is None

    async def get_agent_card(self, agent_slug: str = None) -> Optional[A2AAgentCard]:
        """Get agent card from well-known endpoint"""
        try:
            client = self.httpx_client or httpx.AsyncClient()

            # Construct agent card URL
            if agent_slug:
                url = f"{self.base_url}/agents/.well-known/agent-card/{agent_slug}.json"
            else:
                url = f"{self.base_url}/agents/.well-known/agent-card.json"

            logger.info(f"Fetching agent card from: {url}")

            response = await client.get(url, timeout=10.0)
            response.raise_for_status()

            card_data = response.json()
            logger.info(f"Retrieved agent card: {card_data.get('name', 'Unknown')}")

            return A2AAgentCard(card_data)

        except Exception as e:
            logger.error(f"Failed to get agent card from {self.base_url}: {e}")
            return None
        finally:
            if self._own_client and self.httpx_client:
                await self.httpx_client.aclose()

class A2AClient:
    """A2A Protocol Client for agent communication"""

    def __init__(self, target_agent_card: A2AAgentCard, httpx_client: Optional[httpx.AsyncClient] = None):
        self.agent_card = target_agent_card
        self.httpx_client = httpx_client
        self._own_client = httpx_client is None

    async def send_message(self, message: str, context_id: str = None, session_id: str = None) -> Optional[str]:
        """Send message to target agent via A2A protocol"""
        try:
            client = self.httpx_client or httpx.AsyncClient()

            # Get chat endpoint from agent card (try different endpoint names)
            chat_endpoint = (self.agent_card.endpoints.get('jsonrpc') or
                           self.agent_card.endpoints.get('chat') or
                           self.agent_card.endpoints.get('a2a'))

            if not chat_endpoint:
                logger.error("No suitable endpoint found in agent card")
                logger.error(f"Available endpoints: {self.agent_card.endpoints}")
                return None

            logger.info(f"Using endpoint: {chat_endpoint}")

            # Prepare A2A message payload
            message_id = str(uuid4())
            payload = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "messageId": message_id,
                        "role": "user",
                        "parts": [{"text": message}],
                        "contextId": context_id or str(uuid4()),
                        "timestamp": datetime.now().isoformat()
                    }
                },
                "id": message_id
            }

            # Send to agent
            logger.info(f"Sending A2A message to {chat_endpoint}")

            response = await client.post(
                chat_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60.0
            )

            response.raise_for_status()
            result = response.json()

            if result.get("result"):
                # Extract response text from A2A format
                parts = result["result"].get("parts", [])
                if parts and len(parts) > 0:
                    return parts[0].get("text", "No response")

            return result.get("response", "No response received")

        except Exception as e:
            logger.error(f"Failed to send A2A message: {e}")
            return f"Error communicating with agent: {str(e)}"
        finally:
            if self._own_client and self.httpx_client:
                await self.httpx_client.aclose()

class A2AAgentRegistry:
    """Registry for managing A2A agent connections"""

    def __init__(self):
        self._agents: Dict[str, A2AAgentCard] = {}
        self._clients: Dict[str, A2AClient] = {}

    async def register_agent(self, agent_slug: str, base_url: str) -> bool:
        """Register an A2A agent"""
        try:
            resolver = A2ACardResolver(base_url)
            agent_card = await resolver.get_agent_card(agent_slug)

            if agent_card:
                self._agents[agent_slug] = agent_card
                logger.info(f"Registered A2A agent: {agent_slug} ({agent_card.name})")
                return True
            else:
                logger.error(f"Failed to register agent: {agent_slug}")
                return False

        except Exception as e:
            logger.error(f"Error registering agent {agent_slug}: {e}")
            return False

    def get_agent(self, agent_slug: str) -> Optional[A2AAgentCard]:
        """Get registered agent card"""
        return self._agents.get(agent_slug)

    async def get_client(self, agent_slug: str) -> Optional[A2AClient]:
        """Get or create A2A client for agent"""
        if agent_slug in self._clients:
            return self._clients[agent_slug]

        agent_card = self.get_agent(agent_slug)
        if agent_card:
            client = A2AClient(agent_card)
            self._clients[agent_slug] = client
            return client

        return None

    def list_agents(self) -> Dict[str, str]:
        """List all registered agents"""
        return {slug: card.name for slug, card in self._agents.items()}

# Global A2A registry instance
a2a_registry = A2AAgentRegistry()

async def discover_and_register_agents():
    """Auto-discover and register A2A agents from configuration"""
    # This would typically read from Django settings or database
    # For now, we'll use hardcoded values similar to SK example

    default_agents = [
        {"slug": "flight-booking", "url": "http://localhost:9999"},
        {"slug": "hotel-booking", "url": "http://localhost:10000"},
        {"slug": "travel-assistant", "url": "http://localhost:8001"}
    ]

    for agent_config in default_agents:
        await a2a_registry.register_agent(
            agent_config["slug"],
            agent_config["url"]
        )

# Auto-discovery can be triggered on Django startup
async def initialize_a2a_system():
    """Initialize A2A system on startup"""
    logger.info("Initializing A2A system...")
    await discover_and_register_agents()
    logger.info(f"A2A system initialized with {len(a2a_registry._agents)} agents")