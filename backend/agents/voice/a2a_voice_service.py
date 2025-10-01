"""
A2A Voice Service - Real-time voice integration with Gemini Live API
Connects A2A agent system with voice conversations using different voices per agent
Based on official Gemini Live API documentation from Context7
"""

import asyncio
import json
import logging
import os
import base64
import contextlib
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime
from websockets.asyncio.client import connect

import google.generativeai as genai

from ..worker_agents.base import BaseWorkerAgent
from ..worker_agents.worker_manager import WorkerAgentManager
from ..database.neo4j.service import get_neo4j_service

logger = logging.getLogger(__name__)

class A2AVoiceService:
    """A2A Voice Service for real-time agent conversations with different voices"""

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required for voice service")

        # Gemini Live API WebSocket endpoint (from Context7 docs)
        self.host = 'generativelanguage.googleapis.com'
        self.websocket_url = f'wss://{self.host}/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent'
        self.model = 'models/gemini-live-2.5-flash-preview'  # Live API model from docs

        # Audio configuration (from Context7 docs)
        self.audio_config = {
            "sample_rate": 24000,  # Standard rate from docs
            "channels": 1,
            "format": "S16_LE"
        }

        # Voice configurations for each agent type with system instructions
        self.agent_voice_configs = {
            "general-worker": {
                "temperature": 0.7,
                "voice_description": "Warm and helpful general assistant",
                "system_instruction": "You are a general-purpose AI assistant. Speak naturally and conversationally. Keep responses concise but helpful for voice interaction."
            },
            "flight-specialist": {
                "temperature": 0.3,
                "voice_description": "Professional travel specialist",
                "system_instruction": "You are a flight booking specialist. Speak professionally and clearly about flight information, schedules, and travel details."
            },
            "hotel-specialist": {
                "temperature": 0.5,
                "voice_description": "Friendly hospitality specialist",
                "system_instruction": "You are a hotel booking specialist. Speak warmly and helpfully about accommodations, amenities, and hospitality services."
            },
            "travel-assistant": {
                "temperature": 0.6,
                "voice_description": "Energetic travel assistant",
                "system_instruction": "You are a comprehensive travel assistant. Speak enthusiastically about travel planning, destinations, and trip coordination."
            }
        }

        self.neo4j_service = get_neo4j_service()
        self.worker_manager = WorkerAgentManager()
        logger.info(f"A2A Voice Service initialized with Gemini Live API: {self.model}")
        logger.info(f"WebSocket endpoint: {self.websocket_url}")
        logger.info(f"Audio config: {self.audio_config}")

    def get_voice_config_for_agent(self, agent_slug: str) -> Dict[str, Any]:
        """Get voice configuration for specific agent"""
        return self.agent_voice_configs.get(agent_slug, self.agent_voice_configs["general-worker"])

    async def create_voice_session(self, agent_slug: str, context_id: str, user_name: str = "user") -> Dict[str, Any]:
        """Create voice-enabled chat session for specific agent"""
        voice_config = self.get_voice_config_for_agent(agent_slug)

        # Get agent instance
        agent = await self.worker_manager.get_worker(agent_slug)
        if not agent:
            raise ValueError(f"Agent {agent_slug} not found")

        # Create Gemini Live API configuration with voice settings
        live_config = types.LiveConnectConfig(
            response_modalities=["TEXT", "AUDIO"],  # Enable voice output
            temperature=voice_config["temperature"],
            max_output_tokens=2048,
            system_instruction=f"""You are {agent.agent_name}. {agent.agent_description}

Voice Settings:
- Voice: {voice_config['voice_description']}
- Speaking rate: {voice_config['speaking_rate']}
- You should speak naturally and conversationally
- Keep responses concise but helpful for voice interaction

{agent.system_prompt}

When responding via voice:
1. Be conversational and natural
2. Avoid overly long responses (aim for 30-60 seconds)
3. Use appropriate tone for your role
4. If you need to delegate to another agent, explain it clearly to the user
"""
        )

        session_info = {
            "agent_slug": agent_slug,
            "agent_name": agent.agent_name,
            "context_id": context_id,
            "user_name": user_name,
            "voice_config": voice_config,
            "live_config": live_config,
            "created_at": datetime.now().isoformat()
        }

        logger.info(f"Created voice session for {agent_slug} with voice: {voice_config['voice_name']}")
        return session_info

    async def create_live_session(self, agent_slug: str, context_id: str) -> Dict[str, Any]:
        """Create Gemini Live API WebSocket session for agent"""
        voice_config = self.get_voice_config_for_agent(agent_slug)

        # Get agent instance
        agent = await self.worker_manager.get_worker(agent_slug)
        if not agent:
            raise ValueError(f"Agent {agent_slug} not found")

        # Build system instruction combining agent info and voice config
        system_instruction = f"""{agent.agent_description}

{voice_config['system_instruction']}

Current agent: {agent.agent_name}
Voice style: {voice_config['voice_description']}

When responding via voice:
1. Be conversational and natural
2. Keep responses concise (30-60 seconds max)
3. Use appropriate tone for your role
4. If delegating to another agent, explain it clearly

{agent.system_prompt}"""

        return {
            "agent_slug": agent_slug,
            "agent_name": agent.agent_name,
            "context_id": context_id,
            "voice_config": voice_config,
            "system_instruction": system_instruction,
            "websocket_url": f"{self.websocket_url}?key={self.api_key}",
            "model": self.model,
            "audio_config": self.audio_config
        }

    async def process_voice_with_live_api(self, session_info: Dict[str, Any],
                                        audio_data: bytes, session_id: str) -> Dict[str, Any]:
        """Process voice message using Gemini Live API WebSocket (from Context7 docs)"""
        start_time = asyncio.get_event_loop().time()

        try:
            # Connect to Gemini Live API WebSocket
            async with connect(session_info["websocket_url"]) as websocket:
                logger.info(f"Connected to Gemini Live API for {session_info['agent_slug']}")

                # Send initial setup (from Context7 docs pattern)
                initial_request = {
                    'setup': {
                        'model': session_info['model'],
                        'generation_config': {
                            'temperature': session_info['voice_config']['temperature'],
                            'max_output_tokens': 2048,
                            'response_modalities': ['TEXT', 'AUDIO']
                        },
                        'system_instruction': {
                            'parts': [{'text': session_info['system_instruction']}]
                        }
                    }
                }
                await websocket.send(json.dumps(initial_request))

                # Send audio input (from Context7 docs pattern)
                audio_input = self._encode_audio_input(audio_data, session_info['audio_config'])
                await websocket.send(json.dumps(audio_input))

                # Collect response
                text_response = ""
                audio_response = b""

                async for message in websocket:
                    msg = json.loads(message)

                    # Handle text response
                    if 'serverContent' in msg:
                        server_content = msg['serverContent']
                        if 'modelTurn' in server_content:
                            model_turn = server_content['modelTurn']
                            for part in model_turn.get('parts', []):
                                if 'text' in part:
                                    text_response += part['text']
                                elif 'inlineData' in part:
                                    # Handle audio response
                                    audio_data_b64 = part['inlineData'].get('data', '')
                                    if audio_data_b64:
                                        audio_response += base64.b64decode(audio_data_b64)

                        # Check if turn is complete
                        if server_content.get('turnComplete'):
                            break

                # Process through A2A system for delegation logic
                agent = get_worker_agent(session_info["agent_slug"])
                if agent and text_response:
                    # Check if we need delegation by analyzing the response
                    full_response = await agent.process_request(
                        user_input=text_response,  # Use recognized text
                        context_id=session_info["context_id"],
                        session_id=session_id,
                        user_name="voice_user"
                    )

                    # Handle delegation if occurred
                    if "[DELEGATION_OCCURRED:" in full_response:
                        target_agent = full_response.split("[DELEGATION_OCCURRED:")[1].split("]")[0]
                        specialist_response = full_response.split("[SPECIALIST_RESPONSE:")[1].split("]")[0]

                        return {
                            "success": True,
                            "text_response": text_response,
                            "audio_response": audio_response,
                            "delegation_occurred": True,
                            "delegated_to": target_agent,
                            "specialist_response": specialist_response,
                            "agent_slug": session_info["agent_slug"],
                            "response_time": asyncio.get_event_loop().time() - start_time
                        }

                return {
                    "success": True,
                    "text_response": text_response,
                    "audio_response": audio_response,
                    "delegation_occurred": False,
                    "agent_slug": session_info["agent_slug"],
                    "agent_name": session_info["agent_name"],
                    "response_time": asyncio.get_event_loop().time() - start_time
                }

        except Exception as e:
            logger.error(f"Error in Live API voice processing: {e}")
            return {
                "success": False,
                "error": str(e),
                "response_time": asyncio.get_event_loop().time() - start_time
            }

    def _encode_audio_input(self, audio_data: bytes, audio_config: Dict[str, Any]) -> Dict[str, Any]:
        """Encode audio input for Gemini Live API (from Context7 docs)"""
        return {
            'realtimeInput': {
                'mediaChunks': [{
                    'mimeType': f'audio/pcm;rate={audio_config["sample_rate"]}',
                    'data': base64.b64encode(audio_data).decode('UTF-8'),
                }],
            },
        }

    def _encode_text_input(self, text: str) -> Dict[str, Any]:
        """Encode text input for Gemini Live API (from Context7 docs)"""
        return {
            'clientContent': {
                'turns': [{
                    'role': 'USER',
                    'parts': [{'text': text}],
                }],
                'turnComplete': True,
            },
        }


    def list_available_voices(self) -> Dict[str, Dict[str, Any]]:
        """List all available agent voices"""
        return {
            agent_slug: {
                "agent_name": agent_slug.replace('-', ' ').title(),
                "voice_config": config,
                "capabilities": ["text", "voice", "real-time"]
            }
            for agent_slug, config in self.agent_voice_configs.items()
        }

# Global voice service instance
_voice_service: Optional[A2AVoiceService] = None

def get_voice_service() -> A2AVoiceService:
    """Get or create voice service instance"""
    global _voice_service
    if _voice_service is None:
        _voice_service = A2AVoiceService()
    return _voice_service