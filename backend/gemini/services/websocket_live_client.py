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


class VoiceSessionState:
    """Voice session states for A2A coordination"""
    LISTENING = "listening"        # Live API 활성 (사용자 입력 대기)
    PROCESSING = "processing"      # A2A Worker 처리 중 (Live API 일시정지)
    RESPONDING = "responding"      # TTS 응답 중


def safe_log_text(text: str) -> str:
    """Safely encode text for logging, preserving Korean and handling all Unicode"""
    if not text:
        return text

    try:
        # Replace problematic characters for Windows cp949 logging
        safe_text = text.encode('cp949', errors='replace').decode('cp949')
        return safe_text
    except Exception:
        # Final fallback: ASCII only
        safe_text = text.encode('ascii', errors='replace').decode('ascii')
        return safe_text


class WebSocketLiveClient:
    """WebSocket-based Live API client following Context7 best practices"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = 'models/gemini-live-2.5-flash-preview'  # Updated Live API model name
        self.host = 'generativelanguage.googleapis.com'
        self.websocket = None
        self.session_active = False
        self.audio_callback = None
        self.text_callback = None
        # Transcript buffering for Korean text
        self.input_transcript_buffer = []
        self.output_transcript_buffer = []
        self.last_transcript_time = 0
        self.transcript_timeout = 0.5  # 500ms timeout to flush buffer (Korean text needs time to combine)

        # Voice session state management for A2A coordination
        self.session_state = VoiceSessionState.LISTENING  # Start in listening mode

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
                        'response_modalities': ['AUDIO'],  # AUDIO only - TEXT causes "invalid argument" error
                        'speech_config': {
                            'voice_config': {
                                'prebuilt_voice_config': {
                                    'voice_name': voice_name  # Configurable voice per agent
                                }
                            }
                        }
                    },
                    'system_instruction': {
                        'parts': [{'text': 'You are a helpful Korean AI assistant. 당신은 한국어 AI 어시스턴트입니다. 사용자의 음성을 정확히 인식하고 자연스럽게 한국어로 응답하세요. 비행기, 호텔, 여행 등 다양한 주제에 대해 도움을 드립니다.'}]
                    },
                    # Enable transcript support (auto language detection) - per official docs
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
        """Receive and process WebSocket messages with reconnection handling"""
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
            error_msg = str(e)
            logger.error(f"Error in message receiving: {error_msg}")

            # Handle specific error codes that indicate service unavailability
            if "1011" in error_msg or "internal error" in error_msg.lower():
                logger.warning("Gemini Live API service unavailable (1011), will attempt reconnection")
                self.session_active = False
                # Notify callback about connection loss for potential reconnection
                if self.text_callback:
                    await self.text_callback({
                        'type': 'connection_lost',
                        'error': '1011',
                        'message': 'Live API service temporarily unavailable'
                    })
            elif "1007" in error_msg or "invalid frame payload" in error_msg:
                logger.error("Live API connection error (1007), ending session")
                self.session_active = False
        finally:
            self.session_active = False

    async def _handle_server_message(self, data: Dict[str, Any]):
        """Handle server messages following Context7 patterns"""

        # DEBUG: Log all received messages to understand what we're getting
        # Only log if it's not just audio data
        if 'serverContent' in data:
            server_content = data.get('serverContent', {})
            if 'modelTurn' not in server_content or 'inputTranscription' in server_content or 'outputTranscription' in server_content:
                logger.info(f"Received server message: {json.dumps(data, indent=2)[:1000]}...")

        # Handle setup complete
        if 'setupComplete' in data:
            logger.info("Setup complete")
            return

        # Handle server content
        server_content = data.get('serverContent', {})
        if not server_content:
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

        # Handle interruption (Context7 패턴)
        if 'interrupted' in server_content:
            logger.info("Stream interrupted by user")
            # Context7 패턴: interrupt 시 오디오 큐 클리어
            if self.audio_callback:
                await self.audio_callback({
                    'type': 'interrupt',
                    'message': 'Audio queue cleared due to interruption'
                })
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
        """Process model turn data - with A2A coordination - PARALLELIZED"""
        parts = model_turn.get('parts', [])
        logger.info(f"Processing {len(parts)} parts in model turn")

        # Check if Live API responses should be blocked
        if not self.is_live_response_enabled():
            logger.info(f"Live API responses blocked - session state: {self.session_state}")
            return

        # Process all parts in parallel for faster response
        tasks = []
        for i, part in enumerate(parts):
            logger.info(f"Part {i}: {part}")

            # Handle text response - BOTH display and A2A routing through callback
            if 'text' in part and self.text_callback:
                text_response = part['text']
                # Create task instead of awaiting
                task = asyncio.create_task(self.text_callback(text_response))
                tasks.append(task)
                logger.info(f"Live API text response queued: {safe_log_text(text_response[:50])}...")

            # Handle audio response (Context7 pattern) - only if in LISTENING state
            inline_data = part.get('inlineData', {})
            if inline_data and 'data' in inline_data:
                audio_b64 = inline_data['data']
                if audio_b64 and self.audio_callback and self.is_live_response_enabled():
                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                        # Create task instead of awaiting
                        task = asyncio.create_task(self.audio_callback(audio_bytes))
                        tasks.append(task)
                        logger.info(f"Audio chunk queued: {len(audio_bytes)} bytes")
                    except Exception as e:
                        logger.error(f"Failed to decode audio: {e}")
                elif not self.is_live_response_enabled():
                    logger.info(f"Audio response blocked - session state: {self.session_state}")

            # DEBUG: Check for any other fields we might be missing
            if 'text' not in part and 'inlineData' not in part:
                logger.warning(f"Part has no text or inlineData: {part}")

        # Wait for all tasks to complete in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_input_transcript(self, transcript_text: str):
        """Handle input transcript with buffering for Korean text"""
        try:
            if isinstance(transcript_text, bytes):
                transcript_text = transcript_text.decode('utf-8')
            elif not isinstance(transcript_text, str):
                transcript_text = str(transcript_text)

            current_time = time.time()
            self.last_transcript_time = current_time

            # Add to buffer (don't send immediately - wait for flush)
            self.input_transcript_buffer.append(transcript_text)

            # Start timer to flush buffer after timeout
            asyncio.create_task(self._flush_input_buffer_after_delay())

        except UnicodeError as e:
            logger.error(f"Encoding error in input transcript: {e}")

    async def _handle_output_transcript(self, transcript_text: str):
        """Handle output transcript with buffering for Korean text"""
        try:
            # Ensure we have a proper string, avoid double encoding/decoding
            if isinstance(transcript_text, bytes):
                transcript_text = transcript_text.decode('utf-8', errors='replace')
            elif not isinstance(transcript_text, str):
                transcript_text = str(transcript_text)

            # Clean and validate the text
            transcript_text = transcript_text.strip()
            if not transcript_text:
                return

            current_time = time.time()
            self.last_transcript_time = current_time

            # Add to buffer
            self.output_transcript_buffer.append(transcript_text)

            # Start timer to flush buffer
            asyncio.create_task(self._flush_output_buffer_after_delay())

        except Exception as e:
            logger.error(f"Error processing output transcript: {e}")
            # Fallback to safe text
            self.output_transcript_buffer.append("[AI 응답]")

    async def _flush_input_buffer_after_delay(self):
        """Flush input transcript buffer after delay"""
        await asyncio.sleep(self.transcript_timeout)

        current_time = time.time()
        if (current_time - self.last_transcript_time) >= self.transcript_timeout:
            if self.input_transcript_buffer:
                combined_text = ''.join(self.input_transcript_buffer).strip()
                if combined_text:
                    logger.info(f"User transcript: {safe_log_text(combined_text)}")

                    await self.text_callback({
                        'type': 'transcript',
                        'text': combined_text,
                        'sender': 'user',
                        'source': 'live_api_input'
                    })
                self.input_transcript_buffer.clear()

    async def _flush_output_buffer_after_delay(self):
        """Flush output transcript buffer after delay"""
        await asyncio.sleep(self.transcript_timeout)

        current_time = time.time()
        if (current_time - self.last_transcript_time) >= self.transcript_timeout:
            if self.output_transcript_buffer:
                combined_text = ''.join(self.output_transcript_buffer).strip()
                if combined_text:
                    logger.info(f"AI transcript: {safe_log_text(combined_text)}")

                    await self.text_callback({
                        'type': 'transcript',
                        'text': combined_text,
                        'sender': 'ai',
                        'source': 'live_api_output'
                    })
                self.output_transcript_buffer.clear()

    async def send_text(self, text: str, role: str = 'USER'):
        """Send text input"""
        if not self.session_active or not self.websocket:
            logger.error("No active session")
            return

        message = {
            'clientContent': {
                'turns': [{
                    'role': role,
                    'parts': [{'text': text}]
                }],
                'turnComplete': True
            }
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Text sent ({role}): {safe_log_text(text)}")
        except Exception as e:
            logger.error(f"Failed to send text: {e}")

    async def update_voice(self, voice_name: str) -> bool:
        """Update speech voice configuration for subsequent responses"""
        if not self.session_active or not self.websocket:
            logger.error("No active session to update voice")
            return False

        message = {
            'setup': {
                'generation_config': {
                    'speech_config': {
                        'voice_config': {
                            'prebuilt_voice_config': {
                                'voice_name': voice_name
                            }
                        }
                    }
                }
            }
        }

        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Voice updated to {voice_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to update voice: {e}")
            return False

    async def send_audio(self, audio_data: bytes):
        """Send audio input (Context7 pattern)"""
        if not self.session_active or not self.websocket:
            logger.debug("No active session for audio input - skipping")
            return

        # Enhanced audio validation following Context7 patterns
        if len(audio_data) == 0:
            logger.warning("Received empty audio data, skipping")
            return

        # Check if audio is all zeros (indicating no real audio input)
        if all(byte == 0 for byte in audio_data):
            logger.warning("Received null audio data (all zeros), skipping")
            return

        # Additional validation: check for minimum meaningful audio data
        if len(audio_data) < 160:  # At 16kHz, this is about 10ms of audio
            logger.warning(f"Received insufficient audio data ({len(audio_data)} bytes), skipping")
            return

        # Check for reasonable audio data variance (not completely flat)
        # Calculate simple variance to detect if audio has any meaningful signal
        if len(audio_data) >= 4:
            # Convert to signed bytes for variance calculation
            signed_data = [int.from_bytes([b], 'big', signed=True) if b > 127 else b for b in audio_data[:100]]
            variance = sum((x - sum(signed_data) / len(signed_data)) ** 2 for x in signed_data) / len(signed_data)
            if variance < 1.0:  # Very low variance indicates flat/silent audio
                logger.warning(f"Received flat audio data (variance: {variance:.2f}), skipping")
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

    async def send_interrupt(self):
        """Send interrupt signal to Live API (Context7 pattern)"""
        if not self.websocket or not self.session_active:
            logger.warning("Cannot send interrupt: no active session")
            return

        try:
            # Context7 패턴: interrupt 신호 전송
            interrupt_message = {
                'clientContent': {
                    'interrupted': True
                }
            }

            await self.websocket.send(json.dumps(interrupt_message))
            self.session_state = VoiceSessionState.PROCESSING
            logger.info("Live API interrupt signal sent successfully")

        except Exception as e:
            logger.error(f"Failed to send interrupt signal: {e}")

    async def set_responding_state(self):
        """Set state to responding during TTS playback"""
        self.session_state = VoiceSessionState.RESPONDING
        logger.info("Voice session in responding state - TTS playback")

    def is_live_response_enabled(self) -> bool:
        """Check if Live API should generate responses"""
        return self.session_state == VoiceSessionState.LISTENING

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
    """Enhanced continuous voice session using WebSocket client with reconnection"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = WebSocketLiveClient(api_key)
        self.websocket_callback = None
        self.voice_name = "Aoede"
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 5.0  # seconds

    async def start(self, websocket_callback, voice_name="Aoede"):
        """Start continuous voice session with reconnection support"""
        self.websocket_callback = websocket_callback
        self.voice_name = voice_name

        async def handle_audio(audio_bytes):
            """Handle audio from Live API"""
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'audio_chunk',
                    'audio': base64.b64encode(audio_bytes).decode('utf-8')
                })

        async def handle_text(text_data):
            """Handle text from Live API - support both direct text and structured data"""
            if self.websocket_callback:
                # Check for connection_lost message and trigger reconnection
                if isinstance(text_data, dict) and text_data.get('type') == 'connection_lost':
                    if text_data.get('error') == '1011':
                        logger.warning("Received 1011 connection loss, attempting reconnection...")
                        asyncio.create_task(self._attempt_reconnection())
                    await self.websocket_callback(text_data)
                    return

                # Check if it's structured transcript data from WebSocketLiveClient
                if isinstance(text_data, dict):
                    # Already structured data from WebSocketLiveClient._flush_*_buffer_after_delay
                    await self.websocket_callback(text_data)
                else:
                    # Direct text for compatibility - assume AI response
                    await self.websocket_callback({
                        'type': 'transcript',
                        'text': text_data,
                        'sender': 'ai',
                        'source': 'live_api_output'
                    })

        try:
            await self.client.start_session(
                audio_callback=handle_audio,
                text_callback=handle_text,
                voice_name=voice_name
            )

            self.reconnect_attempts = 0  # Reset on successful connection
            logger.info("Continuous voice session started successfully")

        except Exception as e:
            logger.error(f"Failed to start continuous voice session: {e}")
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'voice_session_status',
                    'status': 'error',
                    'message': f'Failed to start session: {str(e)}'
                })

    async def _attempt_reconnection(self):
        """Attempt to reconnect after connection loss"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            if self.websocket_callback:
                await self.websocket_callback({
                    'type': 'voice_session_status',
                    'status': 'reconnection_failed',
                    'message': 'Maximum reconnection attempts reached'
                })
            return

        self.reconnect_attempts += 1
        logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts}...")

        # Notify about reconnection attempt
        if self.websocket_callback:
            await self.websocket_callback({
                'type': 'voice_session_status',
                'status': 'reconnecting',
                'message': f'Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}'
            })

        # Wait before reconnecting
        await asyncio.sleep(self.reconnect_delay)

        try:
            # Create new client instance
            await self.client.end_session()
            self.client = WebSocketLiveClient(self.api_key)

            # Restart session with current callbacks
            await self.start(self.websocket_callback, self.voice_name)

        except Exception as e:
            logger.error(f"Reconnection attempt {self.reconnect_attempts} failed: {e}")
            # Try again if we haven't reached max attempts
            if self.reconnect_attempts < self.max_reconnect_attempts:
                asyncio.create_task(self._attempt_reconnection())

    async def send_text(self, text: str, role: str = 'USER'):
        """Proxy text sending to the underlying WebSocket client"""
        await self.client.send_text(text, role=role)

    async def update_voice(self, voice_name: str) -> bool:
        """Update voice configuration for subsequent Live API turns"""
        return await self.client.update_voice(voice_name)

    # Context7 패턴: interrupt만 사용 (pause/resume 미구현으로 제거)

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