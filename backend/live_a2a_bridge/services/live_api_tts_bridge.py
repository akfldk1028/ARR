"""
Live API + A2A TTS Bridge
Optimized approach for sending A2A responses through Live API TTS
"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)


class LiveAPITTSBridge:
    """
    Bridge to properly send A2A agent responses through Live API TTS

    The key insight: Instead of sending as USER message, we need to trigger
    Live API to generate TTS directly from text.
    """

    def __init__(self, websocket_client):
        self.websocket_client = websocket_client
        self.session_active = False

    async def send_specialist_response_as_tts(self, specialist_response: str, voice_name: str = "Aoede") -> bool:
        """
        Send A2A specialist response as TTS through Live API

        Strategy: Use Live API's generation config to force TTS output
        """
        try:
            if not self.websocket_client.session_active or not self.websocket_client.websocket:
                logger.error("No active Live API session for TTS")
                return False

            # Method 1: Direct TTS generation request
            tts_request = {
                'clientContent': {
                    'turns': [{
                        'role': 'MODEL',  # Use MODEL role instead of USER
                        'parts': [{'text': specialist_response}]
                    }],
                    'turnComplete': True
                }
            }

            await self.websocket_client.websocket.send(json.dumps(tts_request))
            logger.info(f"Specialist response sent for TTS: {specialist_response[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to send specialist response as TTS: {e}")
            return False

    async def send_as_system_injection(self, response_text: str) -> bool:
        """
        Alternative method: Inject response as system message
        """
        try:
            if not self.websocket_client.session_active:
                return False

            # System injection method
            system_message = {
                'setup': {
                    'model': self.websocket_client.model,
                    'generation_config': {
                        'response_modalities': ['AUDIO'],
                        'speech_config': {
                            'voice_config': {
                                'prebuilt_voice_config': {
                                    'voice_name': 'Aoede'
                                }
                            }
                        }
                    },
                    'system_instruction': {
                        'parts': [{'text': f'Say exactly: "{response_text}"'}]
                    }
                }
            }

            await self.websocket_client.websocket.send(json.dumps(system_message))
            logger.info(f"System injection sent: {response_text[:50]}...")
            return True

        except Exception as e:
            logger.error(f"System injection failed: {e}")
            return False


async def create_optimized_voice_callback(original_callback: Callable, bridge: LiveAPITTSBridge) -> Callable:
    """
    Create enhanced voice callback that properly handles A2A responses
    """

    async def enhanced_callback(data):
        """Enhanced callback with proper A2A TTS integration"""
        try:
            # Handle transcript data
            if data.get('type') == 'transcript' and data.get('text'):
                transcript = data.get('text', '').strip()

                # Check for user input
                if transcript.startswith('[USER]:'):
                    user_text = transcript[7:].strip()

                    # Simple delegation check for testing
                    if any(keyword in user_text.lower() for keyword in ['비행기', '항공', 'flight', '예약']):
                        # This would be handled by specialist
                        specialist_response = f"전문가 응답: {user_text}에 대한 항공 전문 답변을 드리겠습니다."

                        # Send through TTS bridge
                        success = await bridge.send_specialist_response_as_tts(specialist_response)

                        if success:
                            # Notify original callback of delegation
                            await original_callback({
                                'type': 'a2a_delegation',
                                'user_input': user_text,
                                'specialist_response': specialist_response,
                                'delegated_agent': 'flight-specialist'
                            })

                    # Forward original transcript
                    await original_callback(data)
                else:
                    # Regular AI response - forward as is
                    await original_callback(data)
            else:
                # Non-transcript data - forward as is
                await original_callback(data)

        except Exception as e:
            logger.error(f"Enhanced callback error: {e}")
            # Fallback to original behavior
            await original_callback(data)

    return enhanced_callback