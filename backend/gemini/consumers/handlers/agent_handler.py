"""
Agent Handler - Agent management and switching functionality
"""

import json
import logging
import time
from typing import Dict, Any

logger = logging.getLogger('gemini.consumers')


class AgentHandler:
    """Handle agent switching, listing, and information requests"""

    def __init__(self, consumer):
        self.consumer = consumer
        self.websocket_send = consumer.send
        self.session_id = consumer.session_id
        self.user_obj = consumer.user_obj
        self.worker_manager = consumer.worker_manager

    async def handle_agent_switch(self, data):
        """Handle agent switching"""
        try:
            new_agent_slug = data.get('agent_slug')
            if not new_agent_slug:
                await self._send_error("Agent slug is required")
                return

            agent = await self.worker_manager.get_worker(new_agent_slug)
            if not agent:
                await self._send_error(f"Agent '{new_agent_slug}' not found")
                return

            old_agent = self.consumer.current_agent_slug
            self.consumer.current_agent_slug = new_agent_slug

            await self.websocket_send(text_data=json.dumps({
                'type': 'agent_switched',
                'old_agent': old_agent,
                'new_agent': new_agent_slug,
                'agent_name': agent.agent_name,
                'success': True,
                'timestamp': time.time()
            }))

            logger.info(f"Agent switched from {old_agent} to {new_agent_slug} for session {self.session_id}")

        except Exception as e:
            logger.error(f"Agent switch error: {e}")
            await self._send_error(f"Failed to switch agent: {str(e)}")

    async def handle_list_agents(self, data):
        """Send list of available agents"""
        try:
            # Get dynamic agent list from worker manager
            available_agents = await self._get_available_agents()

            await self.websocket_send(text_data=json.dumps({
                'type': 'agents_list',
                'current_agent': self.consumer.current_agent_slug,
                'agents': available_agents,
                'success': True,
                'timestamp': time.time()
            }))

        except Exception as e:
            logger.error(f"Agent list error: {e}")
            await self._send_error(f"Failed to list agents: {str(e)}")

    async def handle_agent_info(self, data):
        """Get agent information"""
        try:
            agent_slug = data.get('agent_slug', self.consumer.current_agent_slug)
            agent = await self.worker_manager.get_worker(agent_slug)

            if not agent:
                await self._send_error(f"Agent '{agent_slug}' not found")
                return

            # Get agent capabilities if available
            capabilities = getattr(agent, 'capabilities', [])
            system_prompt = getattr(agent, 'system_prompt', '')

            await self.websocket_send(text_data=json.dumps({
                'type': 'agent_info',
                'agent_slug': agent_slug,
                'agent_name': agent.agent_name,
                'agent_description': agent.agent_description,
                'capabilities': capabilities,
                'system_prompt': system_prompt[:200] + '...' if len(system_prompt) > 200 else system_prompt,
                'is_current': agent_slug == self.consumer.current_agent_slug,
                'success': True,
                'timestamp': time.time()
            }))

        except Exception as e:
            logger.error(f"Agent info error: {e}")
            await self._send_error(f"Failed to get agent info: {str(e)}")

    async def handle_semantic_routing(self, data):
        """Handle semantic routing requests"""
        try:
            user_text = data.get('text', '').strip()
            if not user_text:
                await self._send_error("Text is required for semantic routing")
                return

            # Perform semantic routing analysis
            routing_result = await self._analyze_intent_with_llm(user_text, 'direct')

            await self.websocket_send(text_data=json.dumps({
                'type': 'semantic_routing_result',
                'user_text': user_text,
                'routing_result': routing_result,
                'success': True,
                'timestamp': time.time()
            }))

        except Exception as e:
            logger.error(f"Semantic routing error: {e}")
            await self._send_error(f"Semantic routing failed: {str(e)}")

    async def _get_available_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get available agents with their information"""
        agents = {}

        # Default agent configurations
        agent_configs = {
            "general-worker": {
                "name": "General Assistant",
                "description": "General-purpose AI assistant for various tasks",
                "icon": "🤖"
            },
            "flight-specialist": {
                "name": "Flight Specialist",
                "description": "Expert in flight booking, travel planning, and airline information",
                "icon": "✈️"
            },
            "hotel-specialist": {
                "name": "Hotel Specialist",
                "description": "Specialist in hotel bookings and accommodation services",
                "icon": "🏨"
            },
            "travel-assistant": {
                "name": "Travel Assistant",
                "description": "Comprehensive travel planning and destination expert",
                "icon": "🧳"
            }
        }

        # Check which agents are actually available
        for agent_slug, config in agent_configs.items():
            try:
                agent = await self.worker_manager.get_worker(agent_slug)
                if agent:
                    agents[agent_slug] = {
                        "name": config["name"],
                        "description": config["description"],
                        "icon": config.get("icon", "🤖"),
                        "status": "available",
                        "agent_name": agent.agent_name,
                        "agent_description": agent.agent_description
                    }
                else:
                    agents[agent_slug] = {
                        "name": config["name"],
                        "description": config["description"],
                        "icon": config.get("icon", "🤖"),
                        "status": "unavailable"
                    }
            except Exception as e:
                logger.warning(f"Failed to check agent {agent_slug}: {e}")
                agents[agent_slug] = {
                    "name": config["name"],
                    "description": config["description"],
                    "icon": config.get("icon", "🤖"),
                    "status": "error",
                    "error": str(e)
                }

        return agents

    async def _analyze_intent_with_llm(self, user_text: str, source: str) -> Dict[str, Any]:
        """Analyze user intent using LLM for routing decisions"""
        try:
            # Import here to avoid circular imports
            from ...services.service_manager import get_gemini_service

            gemini_service = get_gemini_service()

            routing_prompt = f"""Analyze this user message and determine the best agent to handle it.

Available agents:
1. general-worker: General assistant for various tasks
2. flight-specialist: Flight booking, airline information, travel schedules
3. hotel-specialist: Hotel bookings, accommodation services
4. travel-assistant: Comprehensive travel planning, destinations

User message: "{user_text}"

Respond with JSON only:
{{
    "should_delegate": true/false,
    "target_agent": "agent-slug" or null,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}"""

            response = await gemini_service.generate_response(
                prompt=routing_prompt,
                session_id=self.session_id,
                response_format="json"
            )

            if response.get('success'):
                try:
                    routing_result = json.loads(response.get('response', '{}'))

                    # Validate routing result
                    if not isinstance(routing_result, dict):
                        raise ValueError("Invalid JSON response")

                    # Ensure required fields
                    routing_result.setdefault('should_delegate', False)
                    routing_result.setdefault('target_agent', None)
                    routing_result.setdefault('confidence', 0.5)
                    routing_result.setdefault('reason', 'No specific routing needed')

                    return routing_result

                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse routing response: {e}")
                    return {
                        'should_delegate': False,
                        'target_agent': None,
                        'confidence': 0.0,
                        'reason': 'Failed to parse routing decision'
                    }
            else:
                logger.error(f"Routing analysis failed: {response.get('error')}")
                return {
                    'should_delegate': False,
                    'target_agent': None,
                    'confidence': 0.0,
                    'reason': 'Routing analysis service unavailable'
                }

        except Exception as e:
            logger.error(f"Semantic routing analysis error: {e}")
            return {
                'should_delegate': False,
                'target_agent': None,
                'confidence': 0.0,
                'reason': f'Error in routing analysis: {str(e)}'
            }

    async def _send_error(self, message: str):
        """Send error message to frontend"""
        await self.websocket_send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': time.time()
        }))