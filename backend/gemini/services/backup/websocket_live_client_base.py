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
        self.model = 'models/gemini-live-2.5-flash-preview'  # Correct Gemini 2.5 Flash Live API model
        self.host = 'generativelanguage.googleapis.com'
        self.websocket = None
        self.session_active = False
        self.audio_callback = None
        self.text_callback = None
        # Transcript buffering for Korean text
        self.input_transcript_buffer = []
        self.output_transcript_buffer = []
        self.last_transcript_time = 0
        self.transcript_timeout = 0.5  # 500ms timeout to flush buffer

    async def start_session(self,
                           audio_callback: Optional[Callable] = None,
                           text_callback: Optional[Callable] = None,
                           voice_name: str = "Aoede"):
        """Start WebSocket session following Context7 patterns"""

        self.audio_callback = audio_callback
        self.text_callback = text_callback

        # Build WebSocket URL
        ws_url = f'wss://{self.host}/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={self.api_key}'

        try:
            logger.info(f"Connecting to WebSocket: {ws_url}")
            self.websocket = await connect(ws_url)
            self.session_active = True

            # Send initial setup request following Context7 patterns WITH TRANSCRIPT SUPPORT
            initial_request = {
                'setup': {
                    'model': self.model,
                    'generation_config': {
                        'response_modalities': ['AUDIO'],  # Audio only - TEXT causes issues
                        'speech_config': {
                            'voice_config': {
                                'prebuilt_voice_config': {
                                    'voice_name': voice_name  # Configurable voice per agent
                                }
                            }
                        }
                    },
                    'system_instruction': {
                        'parts': [{'text': 'You are a Korean AI assistant. The user will speak in Korean language. Please recognize Korean speech correctly and respond naturally in Korean. Do not confuse Korean with Arabic or other languages. 당신은 한국어 AI 어시스턴트입니다. 사용자는 한국어로 말할 것입니다. 한국어 음성을 정확히 인식하고 자연스럽게 한국어로 응답해주세요.'}]
                    },
                    # CRITICAL: Enable transcript support for both input and output
                    'input_audio_transcription': {},  # Transcribe user speech
                    'output_audio_transcription': {}  # Transcribe AI speech
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

        # DEBUG: Log all received messages to understand what we're getting
        logger.info(f"Received server message: {json.dumps(data, indent=2)[:500]}...")

        # Handle setup complete
        if 'setupComplete' in data:
            logger.info("Setup complete")
            return

        # Handle server content
        server_content = data.get('serverContent', {})
        if not server_content:
            logger.debug("No serverContent in message")
            return

        # CRITICAL: Handle transcript messages with buffering for Korean text
        if 'inputTranscription' in server_content and self.text_callback:
            transcript_text = server_content['inputTranscription'].get('text', '')
            if transcript_text:
                await self._handle_input_transcript(transcript_text)

        if 'outputTranscription' in server_content and self.text_callback:
            transcript_text = server_content['outputTranscription'].get('text', '')
            if transcript_text:
                await self._handle_output_transcript(transcript_text)

        # Handle interruption
        if 'interrupted' in server_content:
            logger.info("Stream interrupted by user")
            return

        # Handle model turn
        model_turn = server_content.get('modelTurn', {})
        if model_turn:
            logger.info(f"Processing model turn: {model_turn}")
            await self._process_model_turn(model_turn)

        # Handle turn complete
        if server_content.get('turnComplete'):
            logger.info("Turn complete")

    async def _process_model_turn(self, model_turn: Dict[str, Any]):
        """Process model turn data"""
        parts = model_turn.get('parts', [])
        logger.info(f"Processing {len(parts)} parts in model turn")

        for i, part in enumerate(parts):
            logger.info(f"Part {i}: {part}")

            # Handle text response - BOTH display and A2A routing through callback
            if 'text' in part and self.text_callback:
                text_response = part['text']

                # Send as formatted transcript data for Consumer processing
                await self.text_callback(text_response)
                logger.info(f"Live API text response sent to callback: {text_response[:50]}...")
                logger.info(f"AI response marked for A2A processing: {text_response[:50]}...")

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

            # DEBUG: Check for any other fields we might be missing
            if 'text' not in part and 'inlineData' not in part:
                logger.warning(f"Part has no text or inlineData: {part}")

    async def _handle_input_transcript(self, transcript_text: str):
        """Handle input transcript with buffering for Korean text"""
        try:
            if isinstance(transcript_text, bytes):
                transcript_text = transcript_text.decode('utf-8')
            transcript_text = str(transcript_text).encode('utf-8').decode('utf-8')

            current_time = time.time()
            self.last_transcript_time = current_time

            # Add to buffer
            self.input_transcript_buffer.append(transcript_text)

            # Start timer to flush buffer
            asyncio.create_task(self._flush_input_buffer_after_delay())

        except UnicodeError as e:
            logger.error(f"Encoding error in input transcript: {e}")

    async def _handle_output_transcript(self, transcript_text: str):
        """Handle output transcript with buffering for Korean text"""
        try:
            if isinstance(transcript_text, bytes):
                transcript_text = transcript_text.decode('utf-8')
            transcript_text = str(transcript_text).encode('utf-8').decode('utf-8')

            current_time = time.time()
            self.last_transcript_time = current_time

            # Add to buffer
            self.output_transcript_buffer.append(transcript_text)

            # Start timer to flush buffer
            asyncio.create_task(self._flush_output_buffer_after_delay())

        except UnicodeError as e:
            logger.error(f"Encoding error in output transcript: {e}")

    async def _flush_input_buffer_after_delay(self):
        """Flush input transcript buffer after delay"""
        await asyncio.sleep(self.transcript_timeout)

        current_time = time.time()
        if (current_time - self.last_transcript_time) >= self.transcript_timeout:
            if self.input_transcript_buffer:
                combined_text = ''.join(self.input_transcript_buffer).strip()
                if combined_text:
                    logger.info(f"User transcript: {combined_text}")
                    await self.text_callback(f"[USER]: {combined_text}")
                self.input_transcript_buffer.clear()

    async def _flush_output_buffer_after_delay(self):
        """Flush output transcript buffer after delay"""
        await asyncio.sleep(self.transcript_timeout)

        current_time = time.time()
        if (current_time - self.last_transcript_time) >= self.transcript_timeout:
            if self.output_transcript_buffer:
                combined_text = ''.join(self.output_transcript_buffer).strip()
                if combined_text:
                    logger.info(f"AI transcript: {combined_text}")
                    await self.text_callback(combined_text)
                self.output_transcript_buffer.clear()

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

        # Validate audio data - check if it's not all zeros (null bytes)
        if len(audio_data) == 0:
            logger.warning("Received empty audio data, skipping")
            return

        # Check if audio is all zeros (indicating no real audio input)
        if all(byte == 0 for byte in audio_data):
            logger.warning("Received null audio data (all zeros), skipping")
            return

        # Convert audio to base64 following Context7 pattern
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')

        message = {
            'realtimeInput': {
                'mediaChunks': [{
                    'mimeType': 'audio/pcm;rate=16000',  # Input at 16kHz as per Context7
                    'data': audio_b64
                }]
            }
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Audio sent: {len(audio_data)} bytes")
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")
            # If we get a connection error, mark session as inactive
            if "1007" in str(e) or "invalid frame payload" in str(e):
                logger.error("Live API connection error, ending session")
                self.session_active = False

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

    async def start(self, websocket_callback, voice_name="Aoede"):
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
                text_callback=handle_text,
                voice_name=voice_name
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