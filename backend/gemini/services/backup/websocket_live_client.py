"""
Websocket-based Live API client implementation
Based on Context7 Cookbook patterns for robust WebSocket communication
"""

import asyncio
import json
import base64
import logging
import re
from typing import Optional, Dict, Any, Callable
from websockets.asyncio.client import connect
import time

logger = logging.getLogger(__name__)

def safe_log_text(text: str) -> str:
    """Safely log text without encoding issues for Korean characters"""
    if not text:
        return ""
    try:
        # Handle encoding issues properly for logging on Windows cp949
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')
        # Convert to string and handle any unicode issues
        safe_text = str(text)
        # Replace characters that can't be displayed in cp949 console
        safe_text = safe_text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        return safe_text[:200]  # Increase limit for better debugging
    except Exception as e:
        return f"[ENCODING_ERROR: {str(e)[:50]}]"


class WebSocketLiveClient:
    """WebSocket-based Live API client following Context7 best practices"""

    def __init__(self, api_key: str, gemini_service=None):
        self.api_key = api_key
        self.model = 'models/gemini-live-2.5-flash-preview'  # User confirmed working model
        self.host = 'generativelanguage.googleapis.com'
        self.websocket = None
        self.session_active = False
        self.audio_callback = None
        self.text_callback = None
        self.gemini_service = gemini_service
        self.a2a_processor = None
        # Transcript buffering for Korean text
        self.input_transcript_buffer = []
        self.output_transcript_buffer = []
        self.last_transcript_time = 0
        self.transcript_timeout = 0.5  # 500ms timeout to flush buffer
        self.pending_user_input = None  # Store user input until Live API responds

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

            # Send initial setup request - CLEAN KOREAN LANGUAGE SUPPORT
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
                            },
                            'language_code': 'ko-KR'  # Korean language for TTS
                        }
                    },

                    'system_instruction': {
                        'parts': [{
                            'text': '''You are a Korean voice recognition and routing assistant.

Role: Analyze user requests and route them to appropriate specialist agents.

IMPORTANT: When you hear words that sound like "필리핀", "비행기", "플라이트", "항공", "공항", "여행" - these are ALL flight-related requests.

Routing Rules:
- Flight/Airline Keywords: 비행기, 항공편, 항공, 플라이트, 공항, 비행, 항공권, 표, 예약, 항공사, 필리핀(often misheard as 비행기)
  → "네, 알겠습니다. 비행기 예약 전문가를 통해 도와드리겠습니다."
- Hotel Keywords: 호텔, 숙박, 머물, 체크인, 룸, 리조트
  → "네, 알겠습니다. 호텔 예약 전문가를 통해 도와드리겠습니다."
- Car Rental Keywords: 렌터카, 차, 운전, 자동차
  → "네, 알겠습니다. 렌터카 예약 전문가를 통해 도와드리겠습니다."
- General conversation → Respond directly

When routing to specialists, use the pattern: "네, 알겠습니다. [SPECIALIST_NAME] 전문가를 통해 도와드리겠습니다."

Language: ALWAYS respond ONLY in Korean language. Never use any other language.'''
                        }]
                    },

                    # ENABLE TRANSCRIPTION (AUTO-DETECT LANGUAGE)
                    'input_audio_transcription': {},
                    'output_audio_transcription': {}
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
            logger.info(f"LIVE API MODEL TURN: Processing {len(model_turn.get('parts', []))} part(s)")
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

            # Handle text response - check for routing and process A2A
            if 'text' in part:
                text_response = part['text']
                logger.info(f"Live API text response: {text_response}")

                # Display the Live API response
                if self.text_callback:
                    await self.text_callback({
                        'type': 'transcript',
                        'text': text_response
                    })

                # Check if we have pending user input for A2A processing
                # Only trigger A2A if Live API response contains "~를 통해 도와드리겠습니다" pattern
                if self.pending_user_input and self.a2a_processor:
                    # Check if Live API response indicates agent delegation using pattern
                    delegation_pattern = "를 통해 도와드리겠습니다"

                    should_trigger_a2a = delegation_pattern in text_response

                    if should_trigger_a2a:
                        logger.info(f"Live API response contains delegation pattern: '{safe_log_text(text_response[:100])}'")
                        logger.info("Processing pending user input with semantic routing A2A system...")

                        # Wait a moment for Live API to finish speaking, then process with A2A
                        await asyncio.sleep(2.0)  # Wait for Live API audio to finish
                        await self._process_pending_a2a_request('semantic-routing')
                    else:
                        # Live API handled directly without delegation - clear pending input
                        logger.info(f"Live API handled directly without agent delegation: '{safe_log_text(text_response[:50])}'")
                        self.pending_user_input = None

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
            logger.info(f"User input transcript: '{safe_log_text(transcript_text)}'")

            # Filter noise
            if '<noise>' in transcript_text.lower() or not transcript_text.strip():
                return

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
        # Google's recommended precision timing pattern
        await asyncio.sleep(10**-12)

        current_time = time.time()
        time_since_last = current_time - self.last_transcript_time

        # Fix floating-point precision issue with epsilon (increased tolerance for Korean speech patterns)
        if time_since_last >= (self.transcript_timeout - 0.01):
            if self.input_transcript_buffer:
                combined_text = ''.join(self.input_transcript_buffer).strip()
                if combined_text:
                    logger.info(f"User said: '{safe_log_text(combined_text)}'")

                    # Send to text callback for display
                    if self.text_callback:
                        await self.text_callback({
                            'type': 'user_transcript',
                            'text': combined_text
                        })

                    # Store the user input for later A2A processing
                    # Don't process with A2A immediately - let Live API respond first
                    self.pending_user_input = combined_text
                    logger.info("Stored user input, waiting for Live API response...")

                self.input_transcript_buffer.clear()

    async def _flush_output_buffer_after_delay(self):
        """Flush output transcript buffer after delay"""
        await asyncio.sleep(self.transcript_timeout)
        # Google's recommended precision timing pattern
        await asyncio.sleep(10**-12)

        current_time = time.time()
        time_since_last = current_time - self.last_transcript_time
        # Fix floating-point precision issue with epsilon (increased tolerance for Korean speech patterns)
        if time_since_last >= (self.transcript_timeout - 0.01):
            if self.output_transcript_buffer:
                combined_text = ''.join(self.output_transcript_buffer).strip()
                if combined_text:
                    logger.info(f"AI transcript: {safe_log_text(combined_text)}")
                    if self.text_callback:
                        await self.text_callback({
                            'type': 'transcript',
                            'text': combined_text
                        })
                self.output_transcript_buffer.clear()




    async def _process_pending_a2a_request(self, routing_mode: str):
        """Process pending user input with A2A after Live API routing"""
        if not self.pending_user_input or not self.a2a_processor:
            return

        try:
            user_input = self.pending_user_input
            self.pending_user_input = None  # Clear pending input

            logger.info(f"Processing A2A request with semantic routing for: '{safe_log_text(user_input)}'")

            # Process with A2A using our existing semantic router
            a2a_result = await self.a2a_processor(user_input)

            if a2a_result and a2a_result.get('success') and a2a_result.get('response'):
                agent_response = a2a_result['response']
                agent_slug = a2a_result.get('agent_slug', 'semantic-agent')
                agent_name = a2a_result.get('agent_name', agent_slug)

                logger.info(f"A2A response from {agent_name}: {agent_response[:100]}...")

                # Generate TTS with different voice for agent
                if self.gemini_service:
                    agent_voice = 'Charon'  # Male voice for agent
                    logger.info(f"Generating agent TTS with {agent_voice} voice")

                    tts_result = await self.gemini_service.process_text_with_audio_streaming(
                        agent_response, agent_voice, "a2a_session", callback=None
                    )

                    if tts_result.get('success') and tts_result.get('audio'):
                        # Send agent audio to user
                        if self.audio_callback:
                            await self.audio_callback(tts_result['audio'])
                            logger.info(f"Agent TTS sent with {agent_voice} voice")

                    # Send transcript to frontend
                    if self.text_callback:
                        await self.text_callback({
                            'type': 'agent_response',
                            'text': agent_response,
                            'agent': agent_name
                        })

        except Exception as e:
            logger.error(f"Error in _process_pending_a2a_request: {e}")

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

    def __init__(self, api_key: str, gemini_service=None):
        self.client = WebSocketLiveClient(api_key, gemini_service=gemini_service)
        self.websocket_callback = None
        self.a2a_processor = None
        self.gemini_service = gemini_service

    async def start(self, websocket_callback, voice_name="Charon", a2a_processor=None):
        """Start continuous voice session"""
        self.websocket_callback = websocket_callback
        self.a2a_processor = a2a_processor

        async def handle_audio(audio_bytes):
            """Handle audio from Live API"""
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'audio_chunk',
                    'audio': base64.b64encode(audio_bytes).decode('utf-8')
                })

        async def handle_text(message_data):
            """Handle text from Live API and trigger A2A delegation when needed"""
            logger.info(f"handle_text called with: '{message_data}'")

            # Extract text content for semantic analysis
            text_content = ""
            if isinstance(message_data, dict):
                text_content = message_data.get('text', '')
            else:
                text_content = str(message_data)

            # Semantic routing: Check if Live API is indicating delegation to specialist
            should_delegate_flight = any(phrase in text_content for phrase in [
                "비행기 예약 전문가를 통해",
                "항공편 전문가에게",
                "flight specialist",
                "aviation expert"
            ])

            # Send response to frontend first
            if self.websocket_callback:
                # Handle both string and dict format
                if isinstance(message_data, dict):
                    await self.websocket_callback(message_data)
                else:
                    await self.websocket_callback({
                        'type': 'transcript',
                        'text': message_data
                    })

            # Trigger A2A delegation if needed
            if should_delegate_flight and self.a2a_processor:
                logger.info("🔄 Semantic routing detected: Delegating to flight specialist")
                try:
                    # Extract user's original request from context if possible
                    user_request = "비행기 예약 도와주세요"  # Default request

                    # Send to A2A processor
                    a2a_response = await self.a2a_processor(
                        agent_slug="flight-specialist",
                        message=user_request,
                        context_id="voice_session_delegation"
                    )

                    if a2a_response and self.websocket_callback:
                        # Send A2A response to frontend
                        await self.websocket_callback({
                            'type': 'a2a_response',
                            'agent': 'flight-specialist',
                            'message': a2a_response,
                            'delegation_triggered': True
                        })

                except Exception as e:
                    logger.error(f"A2A delegation failed: {e}")
                    if self.websocket_callback:
                        await self.websocket_callback({
                            'type': 'a2a_error',
                            'error': f'Failed to contact flight specialist: {str(e)}'
                        })

        try:
            # Pass a2a_processor to the WebSocket client
            self.client.a2a_processor = a2a_processor

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