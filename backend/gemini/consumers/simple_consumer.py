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
from agents.worker_agents.worker_manager import WorkerAgentManager

logger = logging.getLogger('gemini.consumers')


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
        self.current_agent_slug = "general-worker"
        self.voice_session = None

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

            await self._send_welcome_message()
            logger.info(f"Connection established: {self.session_id}")

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
                            # 사용자 입력에 대해 semantic routing 적용
                            user_text = message.get('text', '')
                            logger.info(f"사용자 입력 transcript: {user_text}")

                            # Semantic routing 수행
                            routing_result = await self._analyze_intent_with_llm(user_text, 'live-api')

                            if routing_result.get('should_delegate', False):
                                # A2A 처리 필요
                                target_agent = routing_result.get('target_agent')
                                logger.info(f"A2A 라우팅: {target_agent}")

                                try:
                                    # A2A 에이전트로 요청 전송
                                    agent = await self.worker_manager.get_worker(target_agent)
                                    if agent:
                                        a2a_response = await agent.process_request(
                                            user_input=user_text,
                                            context_id=self.session_id,
                                            session_id=self.session_id,
                                            user_name=self.user_obj.username if self.user_obj else "user"
                                        )

                                        # A2A 응답을 음성으로 변환하여 전송
                                        voice_name = 'Kore' if target_agent == 'flight-specialist' else 'Aoede'
                                        await self._process_a2a_response(a2a_response, voice_name, user_text)

                                    else:
                                        logger.error(f"Agent {target_agent} not available")
                                        # Fallback to Live API
                                        pass

                                except Exception as e:
                                    logger.error(f"A2A processing failed: {e}")
                                    # Fallback to Live API
                                    pass
                            else:
                                # Live API에서 직접 처리 - transcript만 frontend로 전송
                                logger.info("Live API 직접 처리")

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

            # Connect Context7 Live API session
            await self.voice_session.start(
                websocket_callback=websocket_callback,
                voice_name="Aoede"
            )

            await self._send_voice_status('started', 'Context7 Live API + A2A 브릿지 활성화!')

        except Exception as e:
            logger.error(f"Context7 Live API session start failed: {e}")
            await self._send_voice_status('error', f'연결 실패: {str(e)}')

    async def _handle_stop_voice_session(self, data):
        """Stop Context7 Live API session"""
        try:
            if self.voice_session:
                await self.voice_session.stop()
                self.voice_session = None
            await self._send_voice_status('stopped', 'Context7 Live API 세션 종료')
        except Exception as e:
            logger.error(f"Context7 voice session stop failed: {e}")
            await self._send_error(f"세션 종료 실패: {str(e)}")

    async def _handle_voice_audio_chunk(self, data):
        """Process voice audio chunk with Context7 Live API"""
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

            # Send to Context7 Live API
            await self.voice_session.process_audio(audio_data)

        except Exception as e:
            logger.error(f"Context7 audio processing failed: {e}")
            await self._send_error(f"음성 처리 실패: {str(e)}")

    # ============== 4. A2A PROCESSING ==============

    async def _handle_text(self, data):
        """Handle text messages with A2A integration"""
        content = data.get('message', '').strip()
        if not content or len(content) > 10000:
            await self._send_error("Invalid message content")
            return

        try:
            # Save user message
            user_message = await self._save_message(content, 'text', 'user')

            # Process with A2A
            result = await self._process_with_a2a(content)

            if result['success']:
                # Save and send A2A response
                await self._save_message(result['response'], 'text', 'assistant', {
                    'agent_slug': self.current_agent_slug,
                    'processing_type': 'a2a_agent'
                })

                await self.send(text_data=json.dumps({
                    'type': 'response',
                    'message': result['response'],
                    'user_message_id': str(user_message.id),
                    'agent_slug': self.current_agent_slug,
                    'success': True
                }))
            else:
                # Fallback to Gemini
                await self._fallback_to_gemini(content, user_message)

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

            logger.info(f"A2A delegation: {old_agent} -> {target_agent} for message: {user_message[:50]}...")

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

            logger.info(f"LLM semantic routing analysis for: '{user_message}' with current agent: {current_agent}")

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
        """Use Gemini LLM to analyze user intent and determine routing"""
        try:
            routing_prompt = f"""
당신은 사용자 요청과 전문 에이전트 기능 간의 의미적 유사도를 측정하여 라우팅을 결정하는 AI 시스템입니다.

전문 에이전트 기능 정의:

🔹 flight-specialist (항공 전문가):
- 핵심 기능: 항공편 검색, 예약, 변경, 취소, 항공료 비교, 좌석 선택, 수하물 정보

🔹 hotel-specialist (숙박 전문가):
- 핵심 기능: 호텔 검색, 예약, 체크인/아웃, 객실 서비스, 숙박 정보, 리뷰 확인

사용자 메시지: "{user_message}"

위 사용자 메시지와 각 전문 에이전트의 핵심 기능 간 의미적 유사도를 분석하세요:

1. 사용자 요청의 진짜 의도를 파악
2. 각 전문 에이전트 기능과의 의미적 관련성 측정
3. 가장 높은 유사도를 가진 에이전트 선택 (임계값 0.7 이상)
4. 임계값 이하면 Live API 직접 처리

**중요**: 오직 flight-specialist와 hotel-specialist만 사용 가능합니다.
일반적인 대화, 질문, 정보 요청은 should_delegate=false로 설정하세요.

의미적 유사도 분석 결과를 JSON으로 응답:
{{
    "should_delegate": boolean,
    "target_agent": "flight-specialist" or "hotel-specialist" or null,
    "confidence": float (0.0-1.0),
    "reasoning": "의미적 유사도 분석 결과",
    "intent_category": "flight|hotel|general",
    "similarity_scores": {{
        "flight_similarity": float,
        "hotel_similarity": float
    }}
}}
"""

            # Use Gemini service for intent analysis
            result = await self.gemini_service.process_text_with_streaming(
                routing_prompt, self.session_id, callback=None
            )

            # Parse LLM response
            llm_response = result.get('text', '{}')
            logger.info(f"LLM routing response: {llm_response}")

            try:
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    routing_data = json.loads(json_match.group())
                else:
                    raise ValueError("No JSON found in LLM response")

                # Validate and process the routing decision
                should_delegate = routing_data.get('should_delegate', False)
                target_agent = routing_data.get('target_agent')
                confidence = float(routing_data.get('confidence', 0.0))
                reasoning = routing_data.get('reasoning', 'LLM 분석 완료')
                intent_category = routing_data.get('intent_category', 'general')

                # Additional validation
                if should_delegate and target_agent == current_agent:
                    should_delegate = False
                    reasoning += " (이미 적절한 에이전트 사용 중)"

                return {
                    'should_delegate': should_delegate,
                    'target_agent': target_agent,
                    'confidence': confidence,
                    'analysis': f"LLM 의도 분석: {intent_category} 카테고리",
                    'reasoning': reasoning
                }

            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse LLM routing response: {e}")
                # Fallback to simple logic
                return {
                    'should_delegate': False,
                    'target_agent': None,
                    'confidence': 0.0,
                    'analysis': "LLM 응답 파싱 실패, 현재 에이전트 유지",
                    'reasoning': "LLM 응답을 파싱할 수 없어 기본 라우팅 사용"
                }

        except Exception as e:
            logger.error(f"LLM intent analysis failed: {e}")
            return {
                'should_delegate': False,
                'target_agent': None,
                'confidence': 0.0,
                'analysis': "LLM 분석 실패, 현재 에이전트 유지",
                'reasoning': f"분석 중 오류 발생: {str(e)}"
            }

    # ============== 7. UTILITY METHODS ==============

    async def _process_a2a_response(self, a2a_response: str, voice_name: str, user_text: str):
        """A2A 응답을 TTS로 변환하여 전송"""
        try:
            import base64

            # A2A 응답을 음성으로 변환
            audio_result = await self.gemini_service.process_text_with_audio_streaming(
                a2a_response, voice_name, self.session_id, callback=None
            )

            # 메시지 저장
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

        except Exception as e:
            logger.error(f"A2A 응답 처리 실패: {e}")
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