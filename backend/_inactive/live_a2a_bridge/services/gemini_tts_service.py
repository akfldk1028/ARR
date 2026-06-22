"""
Gemini TTS Service for A2A Response Conversion
Direct integration with Gemini TTS API for voice response generation
"""

import asyncio
import base64
import json
import logging
import requests
from typing import Optional, Dict, Any
from config.api_config import APIConfig
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class GeminiTTSService:
    """
    Service to convert A2A agent responses to voice using Gemini TTS API

    This replaces the problematic send_text() approach with proper TTS generation
    """

    def __init__(self):
        self.api_key = APIConfig.get_api_key('google')
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-2.5-flash-preview-tts"

    async def convert_text_to_audio(self, text: str, voice_name: str = "Aoede") -> Optional[bytes]:
        """
        Convert text to audio using Gemini TTS API

        Args:
            text: Text to convert to speech
            voice_name: Voice to use (Aoede, Charon, Kore, etc.)

        Returns:
            Audio bytes in PCM format, or None if failed
        """
        if not self.api_key:
            logger.error("No Gemini API key configured")
            return None

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return None

        try:
            url = f"{self.base_url}/models/{self.model}:generateContent"

            headers = {
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json"
            }

            # Build request payload following Gemini TTS API format
            payload = {
                "contents": [{
                    "parts": [{"text": text}]
                }],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],  # Key: Request audio output
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice_name
                            }
                        }
                    }
                }
            }

            logger.info(f"Converting to audio: {text[:50]}... (voice: {voice_name})")

            # Use sync_to_async with requests
            response = await sync_to_async(requests.post)(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                response_data = response.json()

                # Extract audio data from response
                audio_data = self._extract_audio_from_response(response_data)

                if audio_data:
                    logger.info(f"TTS conversion successful: {len(audio_data)} bytes")
                    return audio_data
                else:
                    logger.error("No audio data in TTS response")
                    return None
            else:
                logger.error(f"TTS API error {response.status_code}: {response.text}")
                return None

        except asyncio.TimeoutError:
            logger.error("TTS request timed out")
            return None
        except Exception as e:
            logger.error(f"TTS conversion failed: {e}")
            return None

    def _extract_audio_from_response(self, response_data: Dict[str, Any]) -> Optional[bytes]:
        """Extract audio bytes from Gemini TTS API response"""
        try:
            # Navigate the response structure to find audio data
            candidates = response_data.get('candidates', [])
            if not candidates:
                logger.error("No candidates in TTS response")
                return None

            candidate = candidates[0]
            content = candidate.get('content', {})
            parts = content.get('parts', [])

            for part in parts:
                # Look for inline audio data
                inline_data = part.get('inlineData')
                if inline_data and 'data' in inline_data:
                    # Audio data is base64 encoded
                    audio_base64 = inline_data['data']
                    audio_bytes = base64.b64decode(audio_base64)
                    return audio_bytes

            logger.error("No audio data found in TTS response parts")
            return None

        except Exception as e:
            logger.error(f"Failed to extract audio from response: {e}")
            return None

    async def get_voice_for_agent(self, agent_slug: str) -> str:
        """Get the appropriate voice for a given agent"""
        voice_mapping = {
            'test-agent': 'Charon',      # Male, confident
            'flight-specialist': 'Aoede',  # Female, professional
            'hotel-specialist': 'Kore',   # Female, friendly
            'general-worker': 'Leda'      # Female, warm
        }

        return voice_mapping.get(agent_slug, 'Aoede')  # Default to Aoede


class A2ATTSBridge:
    """
    Bridge service that combines A2A processing with TTS conversion

    This is the main service that integrates with simple_consumer.py
    """

    def __init__(self):
        self.tts_service = GeminiTTSService()

    async def process_a2a_response_with_tts(self,
                                          a2a_response: str,
                                          agent_slug: str,
                                          websocket_callback) -> bool:
        """
        Process A2A response and convert to TTS, then send via WebSocket

        Args:
            a2a_response: Text response from A2A agent
            agent_slug: Agent that generated the response
            websocket_callback: Function to send audio back to client

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get appropriate voice for agent
            voice_name = await self.tts_service.get_voice_for_agent(agent_slug)

            # Convert text to audio using TTS
            audio_bytes = await self.tts_service.convert_text_to_audio(a2a_response, voice_name)

            if not audio_bytes:
                logger.error("TTS conversion failed")
                return False

            # Send audio via WebSocket callback
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

            await websocket_callback({
                'type': 'audio_chunk',
                'audio': audio_base64,
                'agent_slug': agent_slug,
                'voice': voice_name,
                'source': 'a2a_tts_bridge'
            })

            # Also send transcript for display
            await websocket_callback({
                'type': 'transcript',
                'text': a2a_response,
                'agent_slug': agent_slug,
                'source': 'a2a_tts_bridge'
            })

            logger.info(f"A2A TTS bridge successful: {agent_slug} -> {voice_name}")
            return True

        except Exception as e:
            logger.error(f"A2A TTS bridge failed: {e}")
            return False


# Global service instance
_tts_bridge: Optional[A2ATTSBridge] = None


def get_a2a_tts_bridge() -> A2ATTSBridge:
    """Get or create global A2A TTS bridge instance"""
    global _tts_bridge
    if _tts_bridge is None:
        _tts_bridge = A2ATTSBridge()
    return _tts_bridge