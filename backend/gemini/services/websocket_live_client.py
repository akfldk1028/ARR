"""
Websocket-based Live API client implementation
Based on Context7 Cookbook patterns for robust WebSocket communication
"""

import asyncio
import json
import base64
import logging
from typing import Optional, Dict, Any, Callable
from websockets.asyncio.client import connect
import time

logger = logging.getLogger(__name__)


class WebSocketLiveClient:
    """WebSocket-based Live API client following Context7 best practices"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = 'models/gemini-2.0-flash-exp'
        self.host = 'generativelanguage.googleapis.com'
        self.websocket = None
        self.session_active = False
        self.audio_callback = None
        self.text_callback = None

    async def start_session(self,
                           audio_callback: Optional[Callable] = None,
                           text_callback: Optional[Callable] = None):
        """Start WebSocket session following Context7 patterns"""

        self.audio_callback = audio_callback
        self.text_callback = text_callback

        # Build WebSocket URL
        ws_url = f'wss://{self.host}/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={self.api_key}'

        try:
            logger.info(f"Connecting to WebSocket: {ws_url}")
            self.websocket = await connect(ws_url)
            self.session_active = True

            # Send initial setup request with Korean language support
            initial_request = {
                'setup': {
                    'model': self.model,
                    'generation_config': {
                        'response_modalities': ['AUDIO'],
                        'speech_config': {
                            'voice_config': {
                                'prebuilt_voice_config': {
                                    'voice_name': 'Puck'  # Puck supports Korean better than Aoede
                                }
                            }
                        },
                        # Optimize for streaming with smaller chunks
                        'candidate_count': 1,
                        'max_output_tokens': 512,
                        'temperature': 0.7
                    },
                    'system_instruction': {
                        'parts': [{
                            'text': """당신은 친근하고 도움이 되는 한국어 AI 어시스턴트입니다.
                            다음 규칙을 따라주세요:
                            - 항상 한국어로 대답해주세요
                            - 자연스럽고 대화하듯이 말해주세요
                            - 질문에 명확하고 유용한 답변을 제공해주세요
                            - 친근하고 정중한 말투를 사용해주세요
                            - 사용자가 영어로 질문해도 한국어로 답변해주세요"""
                        }]
                    }
                }
            }

            await self.websocket.send(json.dumps(initial_request))
            logger.info("Setup request sent successfully")

            # Start receiving messages
            asyncio.create_task(self._receive_messages())

        except Exception as e:
            logger.error(f"Failed to start WebSocket session: {e}")
            self.session_active = False
            raise

    async def _receive_messages(self):
        """Receive and process WebSocket messages"""
        try:
            async for message in self.websocket:
                if not self.session_active:
                    break

                try:
                    data = json.loads(message)
                    await self._handle_server_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

        except Exception as e:
            logger.error(f"Error in message receiving: {e}")
        finally:
            self.session_active = False

    async def _handle_server_message(self, data: Dict[str, Any]):
        """Handle server messages following Context7 patterns"""

        # Handle setup complete
        if 'setupComplete' in data:
            logger.info("Setup complete")
            return

        # Handle server content
        server_content = data.get('serverContent', {})
        if not server_content:
            return

        # Handle interruption
        if 'interrupted' in server_content:
            logger.info("Stream interrupted by user")
            return

        # Handle model turn
        model_turn = server_content.get('modelTurn', {})
        if model_turn:
            await self._process_model_turn(model_turn)

        # Handle turn complete
        if server_content.get('turnComplete'):
            logger.info("Turn complete")

    async def _process_model_turn(self, model_turn: Dict[str, Any]):
        """Process model turn data"""
        parts = model_turn.get('parts', [])

        for part in parts:
            # Handle text response
            if 'text' in part and self.text_callback:
                await self.text_callback(part['text'])
                logger.info(f"Text response: {part['text'][:50]}...")

            # Handle audio response (Context7 pattern)
            inline_data = part.get('inlineData', {})
            if inline_data and 'data' in inline_data:
                audio_b64 = inline_data['data']
                if audio_b64 and self.audio_callback:
                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                        await self.audio_callback(audio_bytes)
                        logger.info(f"Audio chunk processed: {len(audio_bytes)} bytes")
                    except Exception as e:
                        logger.error(f"Failed to process audio: {e}")

    async def send_text(self, text: str):
        """Send text input"""
        if not self.session_active or not self.websocket:
            logger.error("No active session")
            return

        message = {
            'clientContent': {
                'turns': [{
                    'role': 'USER',
                    'parts': [{'text': text}]
                }],
                'turnComplete': True
            }
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Text sent: {text}")
        except Exception as e:
            logger.error(f"Failed to send text: {e}")

    async def send_audio(self, audio_data: bytes):
        """Send audio input (Context7 pattern)"""
        if not self.session_active or not self.websocket:
            logger.error("No active session")
            return

        # Convert audio to base64
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')

        message = {
            'realtimeInput': {
                'mediaChunks': [{
                    'mimeType': 'audio/pcm;rate=16000',
                    'data': audio_b64
                }]
            }
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Audio sent: {len(audio_data)} bytes")
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")

    async def end_session(self):
        """End the session"""
        self.session_active = False

        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocket session ended")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None


class ContinuousVoiceSession:
    """Enhanced continuous voice session using WebSocket client"""

    def __init__(self, api_key: str):
        self.client = WebSocketLiveClient(api_key)
        self.websocket_callback = None

    async def start(self, websocket_callback):
        """Start continuous voice session"""
        self.websocket_callback = websocket_callback

        async def handle_audio(audio_bytes):
            """Handle audio from Live API"""
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'audio_chunk',
                    'audio': base64.b64encode(audio_bytes).decode('utf-8')
                })

        async def handle_text(text):
            """Handle text from Live API"""
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'transcript',
                    'text': text
                })

        try:
            await self.client.start_session(
                audio_callback=handle_audio,
                text_callback=handle_text
            )

            logger.info("Continuous voice session started successfully")

        except Exception as e:
            logger.error(f"Failed to start continuous voice session: {e}")
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'voice_session_status',
                    'status': 'error',
                    'message': f'Failed to start session: {str(e)}'
                })

    async def process_audio(self, audio_data: str):
        """Process audio input (base64 string)"""
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            await self.client.send_audio(audio_bytes)
        except Exception as e:
            logger.error(f"Failed to process audio input: {e}")

    async def stop(self):
        """Stop the session"""
        await self.client.end_session()
        logger.info("Continuous voice session stopped")