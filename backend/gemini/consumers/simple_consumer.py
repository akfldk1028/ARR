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
                """Forward Live API messages to frontend"""
                try:
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

    # ============== 7. UTILITY METHODS ==============

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