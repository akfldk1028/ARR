"""
Clean and Simple Gemini WebSocket Consumer
- Live API + A2A + TTS Integration
- Organized sequential processing
- Clear error handling
"""

import asyncio
import base64
import json
import logging
import time
from typing import Dict, Any, Optional

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import StopConsumer
from asgiref.sync import sync_to_async
from PIL import Image
import io

from ..models import ChatSession, ChatMessage
from ..services.service_manager import get_gemini_service
from ..services.websocket_live_client import ContinuousVoiceSession
from ..services.vad_stt_service import VADSTTService
from agents.worker_agents.worker_manager import WorkerAgentManager

logger = logging.getLogger('gemini.consumers')


def safe_log_text(text: str) -> str:
    """Safely encode text for logging, handling encoding errors"""
    if not text:
        return text
    try:
        # Try to encode and decode to catch problematic characters
        text.encode('utf-8')
        return text
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Replace problematic characters with ASCII representation
        return text.encode('ascii', errors='backslashreplace').decode('ascii')


class SimpleChatConsumer(AsyncWebsocketConsumer):
    """
    Clean WebSocket consumer with organized structure:
    1. Connection Management
    2. Message Routing
    3. Live API Integration
    4. A2A Processing
    5. Database Operations
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.chat_session = None
        self.user_obj = None
        self.gemini_service = None
        self.worker_manager = WorkerAgentManager()
        self.current_agent_slug = "hostagent"
        self.voice_session = None
        self.a2a_handler = None
        self.vad_stt_service = None  # VAD + STT integrated service

        # Neo4j Integration (Required for A2A Handler)
        from agents.database.neo4j.service import get_neo4j_service
        from agents.database.neo4j import ConversationTracker, TaskManager, ProvenanceTracker
        self.neo4j_service = get_neo4j_service()
        self.conversation_tracker = ConversationTracker(self.neo4j_service)
        self.task_manager = TaskManager(self.neo4j_service)
        self.provenance_tracker = ProvenanceTracker(self.neo4j_service)
        self.neo4j_session_id = None  # Neo4j Session ID
        self.turn_counter = 0  # Turn counter for this session

    # ============== 1. CONNECTION MANAGEMENT ==============

    async def connect(self):
        """Initialize connection and session"""
        try:
            await self.accept()

            # Parallel initialization
            self.user_obj = await self._get_user()
            self.gemini_service = get_gemini_service()
            self.chat_session = await self._get_or_create_session()
            self.session_id = str(self.chat_session.id)

            # Neo4j Session 생성
            username = self.user_obj.username if self.user_obj else 'anonymous'
            self.neo4j_session_id = self.conversation_tracker.create_session(
                username,
                metadata={'django_session_id': self.session_id, 'agent': self.current_agent_slug}
            )
            logger.info(f"Neo4j Session created: {self.neo4j_session_id}")

            # Initialize handlers
            from .handlers.a2a_handler import A2AHandler
            self.a2a_handler = A2AHandler(self)

            await self._send_welcome_message()
            logger.info(f"Connection established: Django={self.session_id}, Neo4j={self.neo4j_session_id}")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            await self._send_error(f"Connection failed: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        """Clean disconnect"""
        try:
            if self.voice_session:
                await self.voice_session.stop()
            if self.chat_session:
                await self._update_session_activity()
            logger.info(f"Disconnected: {self.session_id}")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
        finally:
            raise StopConsumer()

    # ============== 2. MESSAGE ROUTING ==============

    async def receive(self, text_data):
        """Route incoming messages to appropriate handlers"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            logger.info(f"Received: {message_type}")

            # Message routing table
            handlers = {
                'text': self._handle_text,
                'text_audio': self._handle_text_audio,
                'audio': self._handle_audio,
                'image': self._handle_image,
                'start_voice_session': self._handle_start_voice_session,
                'stop_voice_session': self._handle_stop_voice_session,
                'voice_audio_chunk': self._handle_voice_audio_chunk,
                'transcript': self._handle_transcript,
                'semantic_routing': self._handle_semantic_routing,
                'a2a_delegation': self._handle_a2a_delegation,
                'session_info': self._handle_session_info,
                'history': self._handle_history,
                'switch_agent': self._handle_agent_switch,
                'list_agents': self._handle_list_agents,
                'agent_info': self._handle_agent_info
            }

            handler = handlers.get(message_type)
            if handler:
                await handler(data)
            else:
                await self._send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self._send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await self._send_error(f"Processing error: {str(e)}")

    # ============== 3. LIVE API INTEGRATION ==============

    async def _handle_start_voice_session(self, data):
        """Start Context7 Live API session with A2A bridge"""
        try:
            from config.api_config import APIConfig

            api_key = APIConfig.get_api_key('google')
            if not api_key:
                await self._send_voice_status('error', 'API key not configured')
                return

            # Get Context7 Live API client
            self.voice_session = ContinuousVoiceSession(api_key)

            # WebSocket callback to send messages to frontend
            async def websocket_callback(message):
                """Handle Live API messages with smart routing"""
                try:
                    message_type = message.get('type')
                    sender = message.get('sender')
                    source = message.get('source')

                    if message_type == 'transcript':
                        if sender == 'user' and source == 'live_api_input':
                            # LiveAPI transcript는 한글 부정확 - 단순 표시용으로만 사용
                            user_text = message.get('text', '')
                            logger.info(f"LiveAPI transcript (표시용): {safe_log_text(user_text)}")

                            # Filter out noise/silence tags from Gemini Live API
                            if user_text.strip() in ['<noise>', '<silence>', '<background>', '']:
                                logger.info(f"Skipping noise/silence tag: {user_text}")
                                return

                            # ❌ A2A routing 제거 - STT transcript만 사용
                            # LiveAPI의 한글 인식이 부정확하므로 A2A routing에 사용하지 않음
                            logger.info("LiveAPI transcript는 A2A routing에 사용하지 않음 (STT 사용)")

                        elif sender == 'ai' and source == 'live_api_output':
                            # AI 출력은 그대로 frontend로 전송
                            logger.info(f"AI 응답 transcript: {message.get('text', '')[:50]}...")

                    elif message_type == 'audio_chunk':
                        # Audio response from AI - 기존과 동일
                        if not message.get('sender'):
                            message['sender'] = 'ai'
                        if not message.get('source'):
                            message['source'] = 'live_api'

                    # 모든 메시지를 frontend로 전송
                    await self.send(text_data=json.dumps(message))

                except Exception as e:
                    logger.error(f"Websocket callback error: {e}")

            # A2A processor callback
            async def a2a_processor(user_text):
                """Process user text through A2A system"""
                try:
                    return await self._process_with_a2a(user_text)
                except Exception as e:
                    logger.error(f"A2A processor error: {e}")
                    return {'success': False, 'error': str(e)}

            # STT transcript callback for A2A routing
            async def stt_transcript_callback(transcript_text):
                """Handle Speech-to-Text transcript results for A2A routing"""
                try:
                    logger.info(f"STT Transcript received: {safe_log_text(transcript_text)}")

                    # Filter out noise/silence
                    if transcript_text.strip() in ['<noise>', '<silence>', '<background>', '']:
                        logger.info(f"Skipping noise/silence: {transcript_text}")
                        return

                    # Send STT transcript to frontend for display
                    await self.send(text_data=json.dumps({
                        'type': 'transcript',
                        'text': transcript_text,
                        'sender': 'user',
                        'source': 'stt'
                    }))
                    logger.info(f"Sent STT transcript to frontend: {safe_log_text(transcript_text)}")

                    # === Neo4j 저장 추가 (음성 입력도 기록) ===
                    turn_id = None  # Initialize for later use
                    if self.neo4j_session_id and self.conversation_tracker:
                        # Create Turn
                        self.turn_counter += 1
                        turn_id = self.conversation_tracker.create_turn(
                            session_id=self.neo4j_session_id,
                            sequence=self.turn_counter,
                            user_query=transcript_text
                        )
                        logger.info(f"Neo4j Turn created for voice: {turn_id}")

                        # Create User Message
                        user_msg_id = self.conversation_tracker.add_message(
                            session_id=self.neo4j_session_id,
                            turn_id=turn_id,
                            role='user',
                            content=transcript_text,
                            sequence=1,
                            metadata={'source': 'stt', 'django_session': self.session_id}
                        )
                        logger.info(f"Neo4j User Message created for voice: {user_msg_id}")

                    # STEP 1: Semantic routing FIRST to determine if interrupt is needed
                    routing_result = await self.a2a_handler._analyze_intent_with_similarity(
                        transcript_text, 'speech-to-text'
                    )

                    if routing_result.get('should_delegate', False):
                        # A2A processing needed - NOW interrupt Live API
                        if self.voice_session and hasattr(self.voice_session, 'send_interrupt'):
                            await self.voice_session.send_interrupt()
                            logger.info("Live API interrupted for A2A processing")

                        target_agent = routing_result.get('target_agent')
                        logger.info(f"STT A2A routing to: {target_agent}")

                        try:
                            # Get agent and process request
                            agent = await self.worker_manager.get_worker(target_agent)
                            if agent:
                                a2a_response = await agent.process_request(
                                    user_input=transcript_text,
                                    context_id=self.session_id,
                                    session_id=self.session_id,
                                    user_name=self.user_obj.username if self.user_obj else "user"
                                )

                                # Convert A2A response to voice
                                voice_name = 'Kore' if target_agent == 'flight-specialist' else 'Aoede'
                                await self._process_a2a_response(a2a_response, voice_name, transcript_text, turn_id)

                                # After A2A TTS completes, Live API auto-resumes on next input
                                logger.info("A2A processing complete - Live API will auto-resume")
                            else:
                                logger.error(f"Agent {target_agent} not available")
                                # Live API will auto-resume since it was interrupted

                        except Exception as e:
                            logger.error(f"STT A2A processing failed: {e}")
                            # Live API will auto-resume since it was interrupted
                    else:
                        # No A2A routing needed - DO NOT interrupt Live API
                        logger.info("STT: No A2A routing needed - Live API continues uninterrupted")

                except Exception as e:
                    logger.error(f"STT transcript callback error: {e}")

            # Start VAD + STT session in parallel
            self.vad_stt_service = VADSTTService(api_key=api_key, vad_engine='silero')
            await self.vad_stt_service.start(transcript_callback=stt_transcript_callback)
            logger.info("VAD + STT service started (Silero VAD, Korean STT)")

            # Connect Context7 Live API session
            await self.voice_session.start(
                websocket_callback=websocket_callback,
                voice_name="Aoede"
            )

            await self._send_voice_status('started', 'Context7 Live API + STT + A2A 브릿지 활성화!')

        except Exception as e:
            logger.error(f"Context7 Live API session start failed: {e}")
            await self._send_voice_status('error', f'연결 실패: {str(e)}')

    async def _handle_stop_voice_session(self, data):
        """Stop Context7 Live API session"""
        try:
            if self.voice_session:
                await self.voice_session.stop()
                self.voice_session = None

            # Stop VAD + STT service
            if self.vad_stt_service:
                await self.vad_stt_service.stop()
                logger.info("VAD + STT service stopped")

            await self._send_voice_status('stopped', 'Context7 Live API + STT 세션 종료')
        except Exception as e:
            logger.error(f"Context7 voice session stop failed: {e}")
            await self._send_error(f"세션 종료 실패: {str(e)}")

    async def _handle_voice_audio_chunk(self, data):
        """Process voice audio chunk with Context7 Live API and Speech-to-Text in parallel"""
        try:
            if not self.voice_session:
                await self._send_error('Live API 세션이 없습니다')
                return

            audio_data = data.get('audio')
            if not audio_data:
                return

            # Basic validation
            try:
                audio_bytes = base64.b64decode(audio_data)
                if len(audio_bytes) < 100 or len(audio_bytes) > 50000:
                    return  # Skip invalid chunks
            except Exception:
                return  # Skip invalid base64

            # Parallel processing: Send to both Live API and VAD+STT
            tasks = [
                self.voice_session.process_audio(audio_data),  # Gemini Live API
            ]

            # Send to VAD + STT if available
            if self.vad_stt_service:
                tasks.append(self.vad_stt_service.process_audio_chunk(audio_data))

            # Run both in parallel
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Context7 audio processing failed: {e}")
            await self._send_error(f"음성 처리 실패: {str(e)}")

    async def _handle_transcript(self, data):
        """Handle transcript messages for A2A routing"""
        try:
            text = data.get('text', '').strip()
            sender = data.get('sender')
            source = data.get('source')

            logger.info(f"Transcript received: sender={sender}, source={source}, text={text[:50]}...")

            # DEDUPLICATION: Skip A2A processing here since websocket_callback already handles it
            # A2A 중복 방지: websocket_callback에서 이미 처리하므로 여기서는 스킵
            if sender == 'user' and source == 'live_api_input' and text:
                logger.info("Transcript A2A processing skipped - already handled in websocket_callback")

            # 모든 transcript 메시지를 frontend로 전송 (기존 동작 유지)
            await self.send(text_data=json.dumps(data))

        except Exception as e:
            logger.error(f"Transcript handling error: {e}")
            await self._send_error(f"Transcript 처리 실패: {str(e)}")

    # ============== 4. A2A PROCESSING ==============

    async def _handle_text(self, data):
        """Handle text messages with A2A integration - Delegate to A2A handler"""
        try:
            # Delegate to A2A handler which includes semantic routing
            await self.a2a_handler.handle_text(data)
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            await self._send_error(f"Text processing failed: {str(e)}")

    async def _handle_text_audio(self, data):
        """Handle text with audio response"""
        content = data.get('message', '').strip()
        voice_name = data.get('voice', 'Aoede')

        if not content:
            await self._send_error("Empty message content")
            return

        try:
            user_message = await self._save_message(content, 'text', 'user')

            # For debugging, skip A2A and go directly to Gemini
            logger.info(f"Processing text_audio with Gemini: {content}")
            await self._process_with_gemini_tts(content, voice_name, user_message)

        except Exception as e:
            logger.error(f"Text audio processing failed: {e}")
            await self._send_error(f"Text audio processing failed: {str(e)}")

    async def _handle_audio(self, data):
        """Handle audio input with transcript and A2A processing"""
        audio_data = data.get('audio', '')
        voice_name = data.get('voice', 'Aoede')

        if not audio_data:
            await self._send_error("No audio data provided")
            return

        try:
            # Decode and validate audio
            audio_bytes = base64.b64decode(audio_data)
            if len(audio_bytes) > 50 * 1024 * 1024:
                await self._send_error("Audio too large (max 50MB)")
                return

            user_message = await self._save_message("[Audio Input] Voice message", 'audio', 'user')

            # Process with Gemini to get transcript
            gemini_result = await self.gemini_service.process_audio_with_audio(
                audio_bytes, voice_name, self.session_id
            )

            user_transcript = gemini_result.get('input_transcript', '')

            if user_transcript:
                # Try A2A processing with transcript
                a2a_result = await self._process_with_a2a(user_transcript)

                if a2a_result['success']:
                    # Generate TTS for A2A response
                    await self._send_a2a_audio_response(
                        a2a_result, user_transcript, voice_name, user_message
                    )
                    return

            # Fallback to original Gemini response
            await self._send_gemini_audio_response(gemini_result, voice_name, user_message)

        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            await self._send_error(f"Audio processing failed: {str(e)}")

    async def _process_with_a2a(self, user_input: str) -> Dict[str, Any]:
        """Core A2A processing logic"""
        try:
            agent = await self.worker_manager.get_worker(self.current_agent_slug)
            if not agent:
                return {'success': False, 'error': 'Agent not available'}

            response = await agent.process_request(
                user_input=user_input,
                context_id=self.session_id,
                session_id=self.session_id,
                user_name=self.user_obj.username if self.user_obj else "user"
            )

            return {
                'success': True,
                'response': response,
                'agent_name': agent.agent_name
            }

        except Exception as e:
            logger.error(f"A2A processing failed: {e}")
            return {'success': False, 'error': str(e)}

    # ============== 5. HELPER METHODS ==============

    async def _process_with_gemini_tts(self, content: str, voice_name: str, user_message):
        """Process text with Gemini TTS"""
        try:
            result = await self.gemini_service.process_text_with_audio_streaming(
                content, voice_name, self.session_id, callback=None
            )

            await self._save_message(result.get('transcript', content), 'audio', 'assistant', {
                'voice': voice_name,
                'has_audio': result['success']
            })

            audio_base64 = None
            if result.get('audio') and result['success']:
                audio_base64 = base64.b64encode(result['audio']).decode('utf-8')

            await self.send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': result.get('transcript', ''),
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'success': result['success']
            }))

        except Exception as e:
            logger.error(f"Gemini TTS processing failed: {e}")
            await self._send_error(f"TTS processing failed: {str(e)}")

    async def _fallback_to_gemini(self, content: str, user_message):
        """Fallback to Gemini when A2A fails"""
        try:
            result = await self.gemini_service.process_text_with_streaming(
                content, self.session_id, callback=None
            )

            await self._save_message(result['text'], 'text', 'assistant', {
                'model': result['model'],
                'fallback_from_a2a': True
            })

            await self.send(text_data=json.dumps({
                'type': 'response',
                'message': result['text'],
                'user_message_id': str(user_message.id),
                'model': result['model'],
                'success': True
            }))

        except Exception as e:
            logger.error(f"Gemini fallback failed: {e}")
            await self._send_error(f"Processing failed: {str(e)}")

    async def _send_a2a_audio_response(self, a2a_result, user_transcript, voice_name, user_message):
        """Send A2A response with TTS"""
        try:
            # Generate TTS for A2A response
            audio_result = await self.gemini_service.process_text_with_audio_streaming(
                a2a_result['response'], voice_name, self.session_id, callback=None
            )

            audio_base64 = None
            if audio_result.get('audio') and audio_result['success']:
                audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

            await self._save_message(a2a_result['response'], 'audio', 'assistant', {
                'agent_slug': self.current_agent_slug,
                'voice': voice_name,
                'has_audio': audio_result['success'],
                'input_transcript': user_transcript
            })

            await self.send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': a2a_result['response'],
                'input_transcript': user_transcript,
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'agent_slug': self.current_agent_slug,
                'success': audio_result['success']
            }))

        except Exception as e:
            logger.error(f"A2A TTS failed: {e}")
            await self._send_error(f"A2A TTS failed: {str(e)}")

    async def _send_gemini_audio_response(self, gemini_result, voice_name, user_message):
        """Send Gemini audio response"""
        try:
            await self._save_message(
                gemini_result.get('transcript', 'No transcript available'),
                'audio', 'assistant', {
                    'voice': voice_name,
                    'has_audio': gemini_result['success'],
                    'input_transcript': gemini_result.get('input_transcript', '')
                }
            )

            audio_base64 = None
            if gemini_result.get('audio') and gemini_result['success']:
                audio_base64 = base64.b64encode(gemini_result['audio']).decode('utf-8')

            await self.send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': gemini_result.get('transcript', ''),
                'input_transcript': gemini_result.get('input_transcript', ''),
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'success': gemini_result['success']
            }))

        except Exception as e:
            logger.error(f"Gemini audio response failed: {e}")
            await self._send_error(f"Gemini audio response failed: {str(e)}")

    # ============== 6. OTHER MESSAGE HANDLERS ==============

    async def _handle_image(self, data):
        """Handle image analysis"""
        image_data = data.get('image', '')
        prompt = data.get('prompt', 'What do you see in this image?')

        if not image_data:
            await self._send_error("No image data provided")
            return

        try:
            # Process image
            image_bytes, mime_type = await self._process_image_data(image_data)
            if not image_bytes:
                return

            user_message = await self._save_message(f"[Image Analysis] {prompt}", 'image', 'user')
            result = await self.gemini_service.process_image(image_bytes, prompt, mime_type)

            await self._save_message(result['text'], 'text', 'assistant', {
                'image_analysis': True,
                'original_prompt': prompt
            })

            await self.send(text_data=json.dumps({
                'type': 'image_response',
                'message': result['text'],
                'prompt': prompt,
                'user_message_id': str(user_message.id),
                'success': True
            }))

        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            await self._send_error(f"Image processing failed: {str(e)}")

    async def _handle_session_info(self, data):
        """Send session information"""
        try:
            message_count = await self._get_message_count()
            await self.send(text_data=json.dumps({
                'type': 'session_info',
                'session_id': self.session_id,
                'user': self.user_obj.username if self.user_obj else 'Anonymous',
                'message_count': message_count,
                'success': True
            }))
        except Exception as e:
            await self._send_error(f"Failed to get session info: {str(e)}")

    async def _handle_history(self, data):
        """Send conversation history"""
        try:
            limit = min(data.get('limit', 50), 100)
            messages = await self._get_recent_messages(limit)
            await self.send(text_data=json.dumps({
                'type': 'history',
                'messages': messages,
                'count': len(messages),
                'success': True
            }))
        except Exception as e:
            await self._send_error(f"Failed to get history: {str(e)}")

    async def _handle_agent_switch(self, data):
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

            old_agent = self.current_agent_slug
            self.current_agent_slug = new_agent_slug

            await self.send(text_data=json.dumps({
                'type': 'agent_switched',
                'old_agent': old_agent,
                'new_agent': new_agent_slug,
                'agent_name': agent.agent_name,
                'success': True
            }))

        except Exception as e:
            await self._send_error(f"Failed to switch agent: {str(e)}")

    async def _handle_list_agents(self, data):
        """Send list of available agents"""
        try:
            agents = {
                "general-worker": {
                    "name": "General Assistant",
                    "description": "General-purpose AI assistant"
                },
                "flight-specialist": {
                    "name": "Flight Specialist",
                    "description": "Flight booking and travel expert"
                }
            }

            await self.send(text_data=json.dumps({
                'type': 'agents_list',
                'current_agent': self.current_agent_slug,
                'agents': agents,
                'success': True
            }))

        except Exception as e:
            await self._send_error(f"Failed to list agents: {str(e)}")

    async def _handle_agent_info(self, data):
        """Get agent information"""
        try:
            agent_slug = data.get('agent_slug', self.current_agent_slug)
            agent = await self.worker_manager.get_worker(agent_slug)

            if not agent:
                await self._send_error(f"Agent '{agent_slug}' not found")
                return

            await self.send(text_data=json.dumps({
                'type': 'agent_info',
                'agent_slug': agent_slug,
                'agent_name': agent.agent_name,
                'agent_description': agent.agent_description,
                'is_current': agent_slug == self.current_agent_slug,
                'success': True
            }))

        except Exception as e:
            await self._send_error(f"Failed to get agent info: {str(e)}")

    async def _handle_a2a_delegation(self, data):
        """Handle A2A delegation requests"""
        try:
            target_agent = data.get('target_agent')
            user_message = data.get('user_message', '')
            delegation_reason = data.get('reason', 'Semantic routing delegation')

            if not target_agent:
                await self._send_error("Target agent is required for delegation")
                return

            if not user_message:
                await self._send_error("User message is required for delegation")
                return

            # Verify target agent exists
            agent = await self.worker_manager.get_worker(target_agent)
            if not agent:
                await self._send_error(f"Target agent '{target_agent}' not found")
                return

            # Switch to target agent
            old_agent = self.current_agent_slug
            self.current_agent_slug = target_agent

            logger.info(f"A2A delegation: {old_agent} -> {target_agent} for message: {safe_log_text(user_message[:50])}...")

            # Process message with new agent
            result = await self._process_with_a2a(user_message)

            if result['success']:
                # Save delegation message
                await self._save_message(user_message, 'text', 'user')
                await self._save_message(result['response'], 'text', 'assistant', {
                    'agent_slug': self.current_agent_slug,
                    'delegated_from': old_agent,
                    'delegation_reason': delegation_reason
                })

                # Get voice for target agent (Flight Agent = 'Kore')
                voice_name = data.get('voice', 'Kore' if target_agent == 'flight-specialist' else 'Aoede')

                # Convert Flight Agent response to TTS using existing Gemini service
                try:
                    audio_result = await self.gemini_service.process_text_with_audio_streaming(
                        result['response'], voice_name, self.session_id, callback=None
                    )

                    audio_base64 = None
                    if audio_result.get('audio') and audio_result['success']:
                        audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

                    # Send A2A response with audio (use existing a2a_response type)
                    await self.send(text_data=json.dumps({
                        'type': 'a2a_response',  # Use existing a2a_response type
                        'agent': agent.agent_name,
                        'message': result['response'],
                        'audio': audio_base64,
                        'voice': voice_name,
                        'agent_slug': target_agent,
                        'original_message': user_message,
                        'delegated_from': old_agent,
                        'reason': delegation_reason,
                        'success': True
                    }))

                except Exception as tts_error:
                    logger.error(f"TTS conversion failed for A2A response: {tts_error}")
                    # Fallback to text-only response
                    await self.send(text_data=json.dumps({
                        'type': 'a2a_response',
                        'agent': agent.agent_name,
                        'message': result['response'],
                        'audio': None,
                        'voice': voice_name,
                        'agent_slug': target_agent,
                        'original_message': user_message,
                        'delegated_from': old_agent,
                        'reason': delegation_reason,
                        'success': True
                    }))
            else:
                # Delegation failed, revert to original agent
                self.current_agent_slug = old_agent
                await self._send_error(f"Delegation to {target_agent} failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"A2A delegation failed: {e}")
            await self._send_error(f"A2A delegation failed: {str(e)}")

    async def _handle_semantic_routing(self, data):
        """Handle LLM-based semantic routing for A2A delegation"""
        try:
            user_message = data.get('user_message', '').strip()
            current_agent = data.get('current_agent', self.current_agent_slug)

            if not user_message:
                await self._send_error("No user message provided for semantic routing")
                return

            logger.info(f"LLM semantic routing analysis for: '{safe_log_text(user_message)}' with current agent: {current_agent}")

            # Use Gemini LLM for semantic intent analysis
            routing_result = await self._analyze_intent_with_llm(user_message, current_agent)

            # Send semantic routing result
            await self.send(text_data=json.dumps({
                'type': 'semantic_routing_result',
                'should_delegate': routing_result['should_delegate'],
                'target_agent': routing_result['target_agent'],
                'confidence': routing_result['confidence'],
                'original_message': user_message,
                'current_agent': current_agent,
                'analysis': routing_result['analysis'],
                'reasoning': routing_result['reasoning'],
                'success': True
            }))

        except Exception as e:
            logger.error(f"Semantic routing failed: {e}")
            await self._send_error(f"Semantic routing failed: {str(e)}")

    async def _analyze_intent_with_llm(self, user_message: str, current_agent: str) -> dict:
        """Use semantic similarity (embeddings) to analyze user intent and determine routing"""
        try:
            from sentence_transformers import SentenceTransformer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            # Load embedding model (cache it in memory)
            if not hasattr(self, '_embedding_model'):
                self._embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

            # Agent capability descriptions
            agent_descriptions = {
                'flight-specialist': '비행기 항공편 항공권 예약 출발 도착 공항 탑승 수하물 좌석 예약 변경 취소 항공료',
                'hotel-specialist': '호텔 숙박 객실 체크인 체크아웃 예약 숙소 리조트 게스트하우스 룸서비스'
            }

            # Compute embeddings
            user_embedding = self._embedding_model.encode([user_message])
            flight_embedding = self._embedding_model.encode([agent_descriptions['flight-specialist']])
            hotel_embedding = self._embedding_model.encode([agent_descriptions['hotel-specialist']])

            # Compute cosine similarities
            flight_similarity = float(cosine_similarity(user_embedding, flight_embedding)[0][0])
            hotel_similarity = float(cosine_similarity(user_embedding, hotel_embedding)[0][0])

            logger.info(f"Semantic similarity - Flight: {flight_similarity:.3f}, Hotel: {hotel_similarity:.3f}")

            # Routing decision based on similarity threshold
            THRESHOLD = 0.5
            max_similarity = max(flight_similarity, hotel_similarity)

            if max_similarity >= THRESHOLD:
                if flight_similarity > hotel_similarity:
                    target_agent = 'flight-specialist'
                    confidence = flight_similarity
                    intent_category = 'flight'
                else:
                    target_agent = 'hotel-specialist'
                    confidence = hotel_similarity
                    intent_category = 'hotel'

                should_delegate = True
                reasoning = f"의미적 유사도 {confidence:.2f}로 {target_agent} 선택"
            else:
                should_delegate = False
                target_agent = None
                confidence = max_similarity
                intent_category = 'general'
                reasoning = f"최대 유사도 {max_similarity:.2f}가 임계값 {THRESHOLD} 미만"

            return {
                'should_delegate': should_delegate,
                'target_agent': target_agent,
                'confidence': confidence,
                'analysis': f"임베딩 기반 의미 분석: {intent_category} 카테고리",
                'reasoning': reasoning,
                'similarity_scores': {
                    'flight_similarity': flight_similarity,
                    'hotel_similarity': hotel_similarity
                }
            }

        except ImportError as e:
            logger.error(f"Sentence Transformers not installed: {e}")
            # Fallback to simple keyword matching
            return await self._fallback_keyword_routing(user_message, current_agent)
        except Exception as e:
            logger.error(f"Semantic analysis failed: {e}")
            return await self._fallback_keyword_routing(user_message, current_agent)

    async def _fallback_keyword_routing(self, user_message: str, current_agent: str) -> dict:
        """Fallback keyword-based routing when embeddings fail"""
        user_lower = user_message.lower()

        flight_keywords = ['비행기', '항공', '비행', '예약', '출발', '도착', '공항', '탑승', '항공권']
        hotel_keywords = ['호텔', '숙박', '체크인', '객실', '숙소', '리조트']

        flight_score = sum(1 for kw in flight_keywords if kw in user_lower) / len(flight_keywords)
        hotel_score = sum(1 for kw in hotel_keywords if kw in user_lower) / len(hotel_keywords)

        if flight_score > hotel_score and flight_score > 0:
            return {
                'should_delegate': True,
                'target_agent': 'flight-specialist',
                'confidence': flight_score,
                'analysis': '키워드 기반 분석: flight 카테고리',
                'reasoning': f'비행 관련 키워드 매칭 점수: {flight_score:.2f}'
            }
        elif hotel_score > 0:
            return {
                'should_delegate': True,
                'target_agent': 'hotel-specialist',
                'confidence': hotel_score,
                'analysis': '키워드 기반 분석: hotel 카테고리',
                'reasoning': f'호텔 관련 키워드 매칭 점수: {hotel_score:.2f}'
            }
        else:
            return {
                'should_delegate': False,
                'target_agent': None,
                'confidence': 0.0,
                'analysis': '키워드 기반 분석: general 카테고리',
                'reasoning': '전문 에이전트 키워드 매칭 없음'
            }

    # ============== 7. UTILITY METHODS ==============

    async def _resume_after_tts_playback(self, estimated_duration: float):
        """TTS 재생 완료 대기 (Context7: interrupt 이후 자동 재개, resume 불필요)"""
        try:
            logger.info(f"Waiting {estimated_duration:.1f}s for TTS playback completion")
            await asyncio.sleep(estimated_duration)
            logger.info(f"TTS playback completed after {estimated_duration:.1f}s (Live API will auto-resume on next input)")
        except Exception as e:
            logger.error(f"Error in TTS playback timer: {e}")

    async def _process_a2a_response(self, a2a_response: str, voice_name: str, user_text: str, turn_id: str = None):
        """A2A 응답을 TTS로 변환하여 전송"""
        try:
            import base64

            # A2A 응답을 음성으로 변환
            audio_result = await self.gemini_service.process_text_with_audio_streaming(
                a2a_response, voice_name, self.session_id, callback=None
            )

            # Django 모델에 메시지 저장
            await self._save_message(user_text, 'text', 'user', {
                'delegated_to_a2a': True,
                'target_agent': voice_name
            })

            await self._save_message(
                audio_result.get('transcript', a2a_response), 'audio', 'assistant', {
                    'voice': voice_name,
                    'has_audio': audio_result['success'],
                    'from_a2a': True,
                    'input_transcript': user_text
                }
            )

            # === Neo4j에 A2A 응답 저장 (음성 플로우) ===
            if turn_id and self.neo4j_session_id and self.conversation_tracker:
                assistant_msg_id = self.conversation_tracker.add_message(
                    session_id=self.neo4j_session_id,
                    turn_id=turn_id,
                    role='assistant',
                    content=a2a_response,
                    sequence=2,
                    metadata={
                        'source': 'a2a',
                        'agent': voice_name,
                        'voice': voice_name,
                        'django_session': self.session_id
                    }
                )
                logger.info(f"Neo4j Assistant Message created for A2A voice response: {assistant_msg_id}")

            # 오디오 응답 전송
            audio_base64 = None
            if audio_result.get('audio') and audio_result['success']:
                audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

            await self.send(text_data=json.dumps({
                'type': 'a2a_audio_response',
                'transcript': a2a_response,
                'audio': audio_base64,
                'voice': voice_name,
                'input_transcript': user_text,
                'success': audio_result['success'],
                'source': 'a2a_agent'
            }))

            logger.info(f"A2A 응답 전송 완료: {voice_name} - {a2a_response[:50]}...")

            # STEP 3: TTS 재생 상태 관리를 위해 RESPONDING 상태로 전환
            if self.voice_session and hasattr(self.voice_session, 'set_responding_state'):
                await self.voice_session.set_responding_state()
                logger.info("A2A TTS response playing - Live API in RESPONDING state")

                # TTS 재생 예상 시간 계산 (대략적으로 텍스트 길이 기반)
                estimated_duration = max(3, len(a2a_response) * 0.08)  # ~80ms per character

                # TTS 재생 완료 대기 (비동기로 처리, Context7는 자동 재개)
                asyncio.create_task(self._resume_after_tts_playback(estimated_duration))
            else:
                # Fallback: 스트리밍 없이 완료 (Context7는 자동 재개)
                logger.info("A2A response completed (Live API will auto-resume on next input)")

        except Exception as e:
            logger.error(f"A2A 응답 처리 실패: {e}")
            # A2A 처리 실패 (Context7는 자동 재개)
            await self._send_error(f"A2A 응답 처리 실패: {str(e)}")

    async def _get_user(self):
        """Get authenticated user"""
        user = self.scope.get("user")
        return user if user and user.is_authenticated else None

    async def _send_welcome_message(self):
        """Send welcome message"""
        model_name = getattr(self.gemini_service.client.config, 'model', 'models/gemini-live-2.5-flash-preview')
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': 'Connected to Gemini Chat',
            'session_id': self.session_id,
            'user': self.user_obj.username if self.user_obj else 'Anonymous',
            'model': model_name,
            'success': True
        }))

    async def _send_voice_status(self, status: str, message: str):
        """Send voice session status"""
        await self.send(text_data=json.dumps({
            'type': 'voice_session_status',
            'status': status,
            'message': message
        }))

    async def _send_error(self, message: str):
        """Send error response"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'success': False
        }))

    async def _process_image_data(self, image_data: str) -> tuple[Optional[bytes], Optional[str]]:
        """Process and validate image data"""
        try:
            # Remove data URL prefix
            if ',' in image_data:
                header, image_data = image_data.split(',', 1)
                if 'data:' in header and ';' in header:
                    mime_type = header.split('data:')[1].split(';')[0]
                else:
                    mime_type = 'image/jpeg'
            else:
                mime_type = 'image/jpeg'

            # Validate image type
            supported_types = {'image/jpeg', 'image/png', 'image/webp'}
            if mime_type not in supported_types:
                await self._send_error(f"Unsupported image type: {mime_type}")
                return None, None

            # Decode and validate
            image_bytes = base64.b64decode(image_data)
            if len(image_bytes) > 10 * 1024 * 1024:
                await self._send_error("Image too large (max 10MB)")
                return None, None

            # Validate with PIL
            image = Image.open(io.BytesIO(image_bytes))
            image.verify()

            return image_bytes, mime_type

        except Exception as e:
            await self._send_error(f"Invalid image data: {str(e)}")
            return None, None

    # ============== 8. DATABASE OPERATIONS ==============

    async def _get_or_create_session(self):
        """Get or create chat session"""
        from django.utils import timezone

        try:
            session = await sync_to_async(ChatSession.objects.get)(
                user=self.user_obj,
                is_active=True
            )
            return session
        except ChatSession.DoesNotExist:
            return await sync_to_async(ChatSession.objects.create)(
                user=self.user_obj,
                is_active=True,
                title=f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                metadata={}
            )

    async def _save_message(self, content: str, message_type: str, sender_type: str, metadata=None):
        """Save message to database"""
        message = await sync_to_async(ChatMessage.objects.create)(
            session=self.chat_session,
            content=content,
            message_type=message_type,
            sender_type=sender_type,
            metadata=metadata or {}
        )
        return message

    async def _get_message_count(self):
        """Get message count for session"""
        return await sync_to_async(self.chat_session.messages.count)()

    async def _get_recent_messages(self, limit: int):
        """Get recent messages"""
        def get_messages():
            messages = self.chat_session.messages.select_related().order_by('-created_at')[:limit]
            return [
                {
                    'id': str(msg.id),
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'sender_type': msg.sender_type,
                    'created_at': msg.created_at.isoformat(),
                    'metadata': msg.metadata
                }
                for msg in reversed(messages)
            ]

        return await sync_to_async(get_messages)()

    async def _update_session_activity(self):
        """Update session activity timestamp"""
        from django.utils import timezone
        if self.chat_session:
            await sync_to_async(ChatSession.objects.filter(id=self.chat_session.id).update)(
                updated_at=timezone.now()
            )