"""
Simplified Gemini WebSocket Consumer
Focus on core functionality with room for future expansion
"""

import asyncio
import base64
import logging
import time
from typing import Dict, Any, Optional
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import StopConsumer
from PIL import Image
import io
import json

from ..models import ChatSession, ChatMessage
from ..services.service_manager import get_gemini_service

# A2A Integration
from agents.worker_agents.worker_manager import WorkerAgentManager
from agents.worker_agents.agent_discovery import AgentDiscoveryService


logger = logging.getLogger('gemini.consumers')


class SimpleChatConsumer(AsyncWebsocketConsumer):
    """
    Simplified WebSocket consumer with:
    - Basic session management
    - Text and image processing
    - Message persistence
    - Clean structure for future expansion
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.chat_session = None
        self.user_obj = None
        self.gemini_service = None

        # A2A Integration
        self.current_agent_slug = "general-worker"  # Default agent
        self.worker_manager = WorkerAgentManager()
        self.discovery_service = None  # Will be initialized later

    async def connect(self):
        """Initialize connection and session - optimized"""
        try:
            # Accept connection immediately for better perceived performance
            await self.accept()

            # Run initialization tasks in parallel
            user_task = asyncio.create_task(self._initialize_user())
            service_task = asyncio.create_task(self._initialize_service())

            # Wait for both to complete
            user, service = await asyncio.gather(user_task, service_task)
            self.user_obj = user
            self.gemini_service = service

            # Get session (can be done after connection is accepted)
            self.chat_session = await self._get_or_create_session()
            self.session_id = str(self.chat_session.id)

            # Send welcome message
            model_name = getattr(self.gemini_service.client.config, 'model', 'models/gemini-2.0-flash-exp')

            await self.send(text_data=json.dumps({
                'type': 'connection',
                'message': 'Connected to Gemini Chat',
                'session_id': self.session_id,
                'user': self.user_obj.username if self.user_obj else 'Anonymous',
                'capabilities': ['text', 'image', 'audio'],
                'model': model_name,
                'success': True
            }))

            logger.info(f"Chat session started: {self.session_id}")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            await self._send_error(f"Connection failed: {str(e)}")
            await self.close()

    async def _initialize_user(self):
        """Initialize user in background"""
        user = self.scope.get("user")
        return user if user and user.is_authenticated else None

    async def _initialize_service(self):
        """Initialize Gemini service"""
        return get_gemini_service()

    async def disconnect(self, close_code):
        """Clean disconnect"""
        try:
            if self.chat_session:
                # Update session activity
                await self._update_session_activity()

            logger.info(f"Chat session ended: {self.session_id}")

        except Exception as e:
            logger.error(f"Disconnect error: {e}")
        finally:
            raise StopConsumer()

    async def receive(self, text_data):
        """Handle incoming messages - optimized pipeline"""
        try:
            # Parse JSON once and cache
            data = json.loads(text_data)
            message_type = data.get('type')

            # DEBUG: Log incoming messages
            logger.info(f"WebSocket received message: type={message_type}, data={data}")

            # Fast path routing without logging overhead in production
            message_handlers = {
                'text': self._handle_text_message,
                'text_audio': self._handle_text_audio_message,
                'audio': self._handle_audio_message,
                'image': self._handle_image_message,
                'session_info': lambda _: self._handle_session_info(),
                'history': self._handle_history_request,
                # A2A Integration
                'switch_agent': self._handle_agent_switch,
                'list_agents': lambda _: self._handle_list_agents(),
                # Continuous Voice Session
                'start_voice_session': lambda _: self._handle_start_voice_session(),
                'stop_voice_session': lambda _: self._handle_stop_voice_session(),
                'voice_audio_chunk': self._handle_voice_audio_chunk,
                'agent_info': self._handle_agent_info,
            }

            handler = message_handlers.get(message_type)
            if handler:
                logger.info(f"Found handler for {message_type}, executing...")
                # Execute handler without additional function call overhead
                if message_type == 'session_info':
                    await handler(None)
                else:
                    await handler(data)
            else:
                await self._send_error(f"Unsupported message type: {message_type}")

        except json.JSONDecodeError:
            await self._send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await self._send_error(f"Processing error: {str(e)}")

    async def _handle_text_message(self, data: Dict[str, Any]):
        """Handle text message processing with A2A integration"""
        content = data.get('message', '').strip()

        if not content:
            await self._send_error("Empty message content")
            return

        if len(content) > 10000:  # 10K character limit
            await self._send_error("Message too long (max 10,000 characters)")
            return

        start_time = time.time()

        try:
            # Save user message first
            user_message_task = asyncio.create_task(
                self._save_message(content, 'text', 'user')
            )

            # Try A2A processing first with streaming support
            async def a2a_streaming_callback(chunk_text):
                """Send A2A response chunks in real-time"""
                await self.send(text_data=json.dumps({
                    'type': 'a2a_streaming_chunk',
                    'chunk': chunk_text,
                    'agent_slug': self.current_agent_slug,
                    'timestamp': time.time()
                }))

            a2a_result = await self._process_with_a2a_agent(content, 'text', callback=a2a_streaming_callback)

            if a2a_result['success']:
                # A2A processing succeeded
                user_message = await user_message_task

                response_text = a2a_result['response']
                agent_name = a2a_result.get('agent_name', 'AI Assistant')

                # Handle agent switching notification
                if a2a_result.get('agent_switched'):
                    await self.send(text_data=json.dumps({
                        'type': 'agent_switched',
                        'old_agent': a2a_result['old_agent'],
                        'new_agent': a2a_result['new_agent'],
                        'agent_name': agent_name,
                        'message': f"Switched to {agent_name} to better help with your request"
                    }))

                # Save assistant response with A2A metadata
                assistant_message_task = asyncio.create_task(
                    self._save_message(
                        response_text, 'text', 'assistant',
                        metadata={
                            'agent_slug': self.current_agent_slug,
                            'agent_name': agent_name,
                            'delegation_occurred': a2a_result.get('delegation_occurred', False),
                            'agent_switched': a2a_result.get('agent_switched', False),
                            'processing_type': 'a2a_agent'
                        },
                        processing_time=time.time() - start_time
                    )
                )

                processing_time = time.time() - start_time

                # Send A2A response
                response_data = {
                    'type': 'response',
                    'message': response_text,
                    'user_message_id': str(user_message.id),
                    'total_processing_time': processing_time,
                    'agent_slug': self.current_agent_slug,
                    'agent_name': agent_name,
                    'delegation_occurred': a2a_result.get('delegation_occurred', False),
                    'agent_switched': a2a_result.get('agent_switched', False),
                    'success': True
                }

                await self.send(text_data=json.dumps(response_data))

                # Complete assistant message save
                try:
                    await assistant_message_task
                except Exception as e:
                    logger.warning(f"A2A assistant message save failed: {e}")

            else:
                # A2A failed, fall back to Gemini service
                logger.info(f"A2A processing failed: {a2a_result.get('error')}, falling back to Gemini")

                # Create streaming callback for real-time response
                async def streaming_callback(chunk_data):
                    """Send chunks immediately as they arrive"""
                    await self.send(text_data=json.dumps({
                        'type': 'streaming_chunk',
                        'chunk': chunk_data.get('chunk', ''),
                        'chunk_id': chunk_data.get('chunk_id', 0),
                        'session_id': chunk_data.get('session_id', self.session_id),
                        'is_final': chunk_data.get('is_final', False)
                    }))

                # Start Gemini processing with streaming callback
                ai_task = asyncio.create_task(
                    self.gemini_service.process_text_with_streaming(content, self.session_id, callback=streaming_callback)
                )

                # Wait for both tasks to complete
                result, user_message = await asyncio.gather(ai_task, user_message_task)

                # Save assistant response in background (don't block response)
                assistant_message_task = asyncio.create_task(
                    self._save_message(
                        result['text'], 'text', 'assistant',
                        metadata={
                            'response_time': result['response_time'],
                            'model': result['model'],
                            'processing_type': result['type'],
                            'fallback_from_a2a': True
                        },
                        processing_time=result['response_time']
                    )
                )

                processing_time = time.time() - start_time

                # Send response immediately (don't wait for assistant message save)
                response_data = {
                    'type': 'response',
                    'message': result['text'],
                    'user_message_id': str(user_message.id),
                    'response_time': result['response_time'],
                    'total_processing_time': processing_time,
                    'model': result['model'],
                    'success': True
                }

                # Send immediately
                await self.send(text_data=json.dumps(response_data))

                # Wait for background save to complete (optional, for cleanup)
                try:
                    assistant_message = await assistant_message_task
                    # Could update with assistant message ID if needed later
                except Exception as e:
                    logger.warning(f"Background save failed: {e}")

        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            await self._send_error(f"Text processing failed: {str(e)}")

    async def _handle_image_message(self, data: Dict[str, Any]):
        """Handle image analysis"""
        image_data = data.get('image', '')
        prompt = data.get('prompt', 'What do you see in this image?')

        if not image_data:
            await self._send_error("No image data provided")
            return

        start_time = time.time()

        try:
            # Validate and process image
            image_bytes, mime_type = await self._process_image_data(image_data)
            if not image_bytes:
                return  # Error already sent

            # Save user message (image prompt)
            user_message = await self._save_message(
                f"[Image Analysis] {prompt}", 'image', 'user',
                metadata={'prompt': prompt, 'mime_type': mime_type}
            )

            # Process with Gemini
            result = await self.gemini_service.process_image(image_bytes, prompt, mime_type)

            # Save assistant response
            assistant_message = await self._save_message(
                result['text'], 'text', 'assistant',
                metadata={
                    'response_time': result['response_time'],
                    'model': result['model'],
                    'processing_type': result['type'],
                    'image_analysis': True,
                    'original_prompt': prompt
                },
                processing_time=result['response_time']
            )

            processing_time = time.time() - start_time

            # Send response
            await self.send(text_data=json.dumps({
                'type': 'image_response',
                'message': result['text'],
                'prompt': prompt,
                'user_message_id': str(user_message.id),
                'assistant_message_id': str(assistant_message.id),
                'response_time': result['response_time'],
                'total_processing_time': processing_time,
                'model': result['model'],
                'success': True
            }))

        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            await self._send_error(f"Image processing failed: {str(e)}")

    async def _handle_text_audio_message(self, data: Dict[str, Any]):
        """Handle text message with audio response (TTS) with A2A integration and continuous mode"""
        content = data.get('message', '').strip()
        voice_name = data.get('voice', 'Aoede')  # Default voice
        continuous_mode = data.get('continuous_mode', False)
        timestamp = data.get('timestamp', time.time())

        if not content:
            await self._send_error("Empty message content")
            return

        if len(content) > 10000:  # 10K character limit
            await self._send_error("Message too long (max 10,000 characters)")
            return

        start_time = time.time()

        # Send immediate acknowledgment for continuous mode
        if continuous_mode:
            await self.send(text_data=json.dumps({
                'type': 'processing_started',
                'message': content,
                'continuous_mode': True,
                'timestamp': timestamp
            }))

        try:
            # Save user message first
            user_message_task = asyncio.create_task(
                self._save_message(content, 'text', 'user')
            )

            # Temporarily skip A2A and go directly to Gemini for debugging
            logger.info(f"Processing text_audio directly with Gemini: {content}")
            a2a_result = {'success': False, 'error': 'A2A temporarily disabled for debugging'}

            if False:  # Force Gemini fallback
                # A2A processing succeeded
                user_message = await user_message_task

                response_text = a2a_result['response']
                agent_name = a2a_result.get('agent_name', 'AI Assistant')

                # Handle agent switching notification
                if a2a_result.get('agent_switched'):
                    await self.send(text_data=json.dumps({
                        'type': 'agent_switched',
                        'old_agent': a2a_result['old_agent'],
                        'new_agent': a2a_result['new_agent'],
                        'agent_name': agent_name,
                        'message': f"Switched to {agent_name} for voice response"
                    }))

                # Use Gemini TTS service for voice synthesis of A2A response
                try:
                    audio_result = await self.gemini_service.process_text_with_audio_streaming(
                        response_text, voice_name, self.session_id, callback=None
                    )

                    # Convert audio to base64 for transmission
                    audio_base64 = None
                    if audio_result.get('audio') and audio_result['success']:
                        import base64
                        audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

                    # Save assistant response with A2A metadata
                    assistant_message_task = asyncio.create_task(
                        self._save_message(
                            response_text, 'audio', 'assistant',
                            metadata={
                                'agent_slug': self.current_agent_slug,
                                'agent_name': agent_name,
                                'delegation_occurred': a2a_result.get('delegation_occurred', False),
                                'agent_switched': a2a_result.get('agent_switched', False),
                                'processing_type': 'a2a_agent_audio',
                                'voice': voice_name,
                                'has_audio': audio_result['success']
                            },
                            processing_time=time.time() - start_time
                        )
                    )

                    processing_time = time.time() - start_time

                    # Wait for assistant message to complete
                    assistant_message = await assistant_message_task

                    # Send A2A audio response
                    await self.send(text_data=json.dumps({
                        'type': 'audio_response',
                        'transcript': response_text,
                        'audio': audio_base64,
                        'voice': voice_name,
                        'user_message_id': str(user_message.id),
                        'assistant_message_id': str(assistant_message.id) if assistant_message else None,
                        'total_processing_time': processing_time,
                        'agent_slug': self.current_agent_slug,
                        'agent_name': agent_name,
                        'delegation_occurred': a2a_result.get('delegation_occurred', False),
                        'agent_switched': a2a_result.get('agent_switched', False),
                        'success': audio_result['success'],
                        'continuous_mode': continuous_mode
                    }))

                    # Send ready signal for continuous mode
                    if continuous_mode:
                        await self.send(text_data=json.dumps({
                            'type': 'ready_for_next',
                            'continuous_mode': True,
                            'message': 'AI response complete, ready for your next question'
                        }))

                except Exception as tts_error:
                    # TTS failed, send text response only
                    logger.warning(f"TTS failed for A2A response: {tts_error}")

                    assistant_message_task = asyncio.create_task(
                        self._save_message(
                            response_text, 'text', 'assistant',
                            metadata={
                                'agent_slug': self.current_agent_slug,
                                'agent_name': agent_name,
                                'delegation_occurred': a2a_result.get('delegation_occurred', False),
                                'agent_switched': a2a_result.get('agent_switched', False),
                                'processing_type': 'a2a_agent_text_fallback',
                                'tts_error': str(tts_error)
                            },
                            processing_time=time.time() - start_time
                        )
                    )

                    assistant_message = await assistant_message_task

                    await self.send(text_data=json.dumps({
                        'type': 'response',
                        'message': response_text,
                        'user_message_id': str(user_message.id),
                        'assistant_message_id': str(assistant_message.id),
                        'total_processing_time': time.time() - start_time,
                        'agent_slug': self.current_agent_slug,
                        'agent_name': agent_name,
                        'delegation_occurred': a2a_result.get('delegation_occurred', False),
                        'agent_switched': a2a_result.get('agent_switched', False),
                        'success': True,
                        'note': 'TTS failed, text response provided',
                        'continuous_mode': continuous_mode
                    }))

                    # Send ready signal for continuous mode
                    if continuous_mode:
                        await self.send(text_data=json.dumps({
                            'type': 'ready_for_next',
                            'continuous_mode': True,
                            'message': 'AI response complete, ready for your next question'
                        }))

            else:
                # A2A failed, fall back to Gemini service
                logger.info(f"A2A processing failed for audio: {a2a_result.get('error')}, falling back to Gemini")

                try:
                    # Create streaming callback for real-time audio response
                    async def audio_streaming_callback(chunk_data):
                        """Send audio chunks immediately as they arrive"""
                        import base64
                        if chunk_data.get('audio_chunk'):
                            # Convert bytes to base64 for JSON serialization
                            audio_base64 = base64.b64encode(chunk_data['audio_chunk']).decode('utf-8')
                            await self.send(text_data=json.dumps({
                                'type': 'audio_streaming_chunk',
                                'audio_chunk': audio_base64,
                                'chunk_id': chunk_data.get('chunk_id', 0),
                                'session_id': chunk_data.get('session_id', self.session_id),
                                'transcript_chunk': chunk_data.get('text_chunk', ''),
                                'is_final': chunk_data.get('is_final', False)
                            }))

                    logger.info(f"Starting Gemini processing for message: {content[:50]}...")

                    # Start AI processing with streaming callback
                    ai_task = asyncio.create_task(
                        self.gemini_service.process_text_with_audio_streaming(content, voice_name, self.session_id, callback=audio_streaming_callback)
                    )

                    logger.info("Gemini task created, waiting for response...")
                except Exception as gemini_error:
                    logger.error(f"Failed to start Gemini processing: {gemini_error}")
                    await self._send_error(f"Gemini processing failed: {str(gemini_error)}")
                    return

                # Wait for both AI and user message save
                try:
                    logger.info("Waiting for Gemini response and user message save...")
                    result, user_message = await asyncio.gather(ai_task, user_message_task)
                    logger.info(f"Gemini response received: success={result.get('success')}, transcript={result.get('transcript', '')[:50]}...")
                except Exception as gather_error:
                    logger.error(f"Failed to get Gemini response: {gather_error}")
                    await self._send_error(f"Gemini response failed: {str(gather_error)}")
                    return

                # Start assistant message save in background
                assistant_message_task = asyncio.create_task(
                    self._save_message(
                        result.get('transcript', content), 'audio', 'assistant',
                        metadata={
                            'response_time': result['response_time'],
                            'model': result['model'],
                            'processing_type': result['type'],
                            'voice': voice_name,
                            'has_audio': result['success'],
                            'fallback_from_a2a': True
                        },
                        processing_time=result['response_time']
                    )
                )

                processing_time = time.time() - start_time

                # Convert audio to base64 for transmission
                audio_base64 = None
                if result.get('audio') and result['success']:
                    import base64
                    audio_base64 = base64.b64encode(result['audio']).decode('utf-8')

                # Wait for assistant message to complete before accessing it
                assistant_message = await assistant_message_task

                # Send response
                await self.send(text_data=json.dumps({
                    'type': 'audio_response',
                    'transcript': result.get('transcript', ''),
                    'audio': audio_base64,
                    'voice': voice_name,
                    'user_message_id': str(user_message.id),
                    'assistant_message_id': str(assistant_message.id) if assistant_message else None,
                    'response_time': result['response_time'],
                    'total_processing_time': processing_time,
                    'model': result['model'],
                    'success': result['success'],
                    'continuous_mode': continuous_mode
                }))

                # Send ready signal for continuous mode
                if continuous_mode:
                    await self.send(text_data=json.dumps({
                        'type': 'ready_for_next',
                        'continuous_mode': True,
                        'message': 'AI response complete, ready for your next question'
                    }))

        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            await self._send_error(f"Audio processing failed: {str(e)}")

    async def _handle_audio_message(self, data: Dict[str, Any]):
        """Handle audio input message (real-time voice input) with A2A integration"""
        audio_data = data.get('audio', '')
        voice_name = data.get('voice', 'Aoede')  # Default voice for response

        if not audio_data:
            await self._send_error("No audio data provided")
            return

        start_time = time.time()

        try:
            # Decode audio data
            audio_bytes = base64.b64decode(audio_data)

            # Size check (50MB limit for audio)
            if len(audio_bytes) > 50 * 1024 * 1024:
                await self._send_error("Audio too large (max 50MB)")
                return

            # Save user audio message
            user_message_task = asyncio.create_task(
                self._save_message(
                    "[Audio Input] Voice message", 'audio', 'user',
                    metadata={'audio_size': len(audio_bytes)}
                )
            )

            # First, get transcript from Gemini Live API
            gemini_result = await self.gemini_service.process_audio_with_audio(
                audio_bytes, voice_name, self.session_id
            )

            user_transcript = gemini_result.get('input_transcript', '')
            if not user_transcript:
                # If no transcript available, fall back to Gemini processing
                user_message = await user_message_task

                assistant_message = await self._save_message(
                    gemini_result.get('transcript', 'No transcript available'), 'audio', 'assistant',
                    metadata={
                        'response_time': gemini_result['response_time'],
                        'model': gemini_result['model'],
                        'processing_type': gemini_result['type'],
                        'voice': voice_name,
                        'has_audio': gemini_result['success'],
                        'input_transcript': gemini_result.get('input_transcript', ''),
                        'a2a_skipped': 'no_transcript'
                    },
                    processing_time=gemini_result['response_time']
                )

                processing_time = time.time() - start_time

                # Convert audio to base64 for transmission
                audio_base64 = None
                if gemini_result.get('audio') and gemini_result['success']:
                    audio_base64 = base64.b64encode(gemini_result['audio']).decode('utf-8')

                await self.send(text_data=json.dumps({
                    'type': 'audio_response',
                    'transcript': gemini_result.get('transcript', ''),
                    'input_transcript': gemini_result.get('input_transcript', 'Processing audio input...'),
                    'audio': audio_base64,
                    'voice': voice_name,
                    'user_message_id': str(user_message.id),
                    'assistant_message_id': str(assistant_message.id),
                    'response_time': gemini_result['response_time'],
                    'total_processing_time': processing_time,
                    'model': gemini_result['model'],
                    'success': gemini_result['success']
                }))
                return

            # Try A2A processing with the transcript
            a2a_result = await self._process_with_a2a_agent(user_transcript, 'audio')

            if a2a_result['success']:
                # A2A processing succeeded
                user_message = await user_message_task

                response_text = a2a_result['response']
                agent_name = a2a_result.get('agent_name', 'AI Assistant')

                # Handle agent switching notification
                if a2a_result.get('agent_switched'):
                    await self.send(text_data=json.dumps({
                        'type': 'agent_switched',
                        'old_agent': a2a_result['old_agent'],
                        'new_agent': a2a_result['new_agent'],
                        'agent_name': agent_name,
                        'message': f"Switched to {agent_name} for voice conversation"
                    }))

                # Use Gemini TTS service for voice synthesis of A2A response
                try:
                    audio_result = await self.gemini_service.process_text_with_audio_streaming(
                        response_text, voice_name, self.session_id, callback=None
                    )

                    # Convert audio to base64 for transmission
                    audio_base64 = None
                    if audio_result.get('audio') and audio_result['success']:
                        import base64
                        audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

                    # Save assistant response with A2A metadata
                    assistant_message = await self._save_message(
                        response_text, 'audio', 'assistant',
                        metadata={
                            'agent_slug': self.current_agent_slug,
                            'agent_name': agent_name,
                            'delegation_occurred': a2a_result.get('delegation_occurred', False),
                            'agent_switched': a2a_result.get('agent_switched', False),
                            'processing_type': 'a2a_agent_voice',
                            'voice': voice_name,
                            'has_audio': audio_result['success'],
                            'input_transcript': user_transcript
                        },
                        processing_time=time.time() - start_time
                    )

                    processing_time = time.time() - start_time

                    # Send A2A audio response
                    await self.send(text_data=json.dumps({
                        'type': 'audio_response',
                        'transcript': response_text,
                        'input_transcript': user_transcript,
                        'audio': audio_base64,
                        'voice': voice_name,
                        'user_message_id': str(user_message.id),
                        'assistant_message_id': str(assistant_message.id),
                        'total_processing_time': processing_time,
                        'agent_slug': self.current_agent_slug,
                        'agent_name': agent_name,
                        'delegation_occurred': a2a_result.get('delegation_occurred', False),
                        'agent_switched': a2a_result.get('agent_switched', False),
                        'success': audio_result['success']
                    }))

                except Exception as tts_error:
                    # TTS failed, send text response only
                    logger.warning(f"TTS failed for A2A audio response: {tts_error}")

                    assistant_message = await self._save_message(
                        response_text, 'text', 'assistant',
                        metadata={
                            'agent_slug': self.current_agent_slug,
                            'agent_name': agent_name,
                            'delegation_occurred': a2a_result.get('delegation_occurred', False),
                            'agent_switched': a2a_result.get('agent_switched', False),
                            'processing_type': 'a2a_agent_voice_text_fallback',
                            'tts_error': str(tts_error),
                            'input_transcript': user_transcript
                        },
                        processing_time=time.time() - start_time
                    )

                    await self.send(text_data=json.dumps({
                        'type': 'response',
                        'message': response_text,
                        'input_transcript': user_transcript,
                        'user_message_id': str(user_message.id),
                        'assistant_message_id': str(assistant_message.id),
                        'total_processing_time': time.time() - start_time,
                        'agent_slug': self.current_agent_slug,
                        'agent_name': agent_name,
                        'delegation_occurred': a2a_result.get('delegation_occurred', False),
                        'agent_switched': a2a_result.get('agent_switched', False),
                        'success': True,
                        'note': 'TTS failed, text response provided'
                    }))

            else:
                # A2A failed, use original Gemini response
                logger.info(f"A2A processing failed for voice input: {a2a_result.get('error')}, using Gemini response")

                user_message = await user_message_task

                assistant_message = await self._save_message(
                    gemini_result.get('transcript', 'No transcript available'), 'audio', 'assistant',
                    metadata={
                        'response_time': gemini_result['response_time'],
                        'model': gemini_result['model'],
                        'processing_type': gemini_result['type'],
                        'voice': voice_name,
                        'has_audio': gemini_result['success'],
                        'input_transcript': user_transcript,
                        'fallback_from_a2a': True
                    },
                    processing_time=gemini_result['response_time']
                )

                processing_time = time.time() - start_time

                # Convert audio to base64 for transmission
                audio_base64 = None
                if gemini_result.get('audio') and gemini_result['success']:
                    audio_base64 = base64.b64encode(gemini_result['audio']).decode('utf-8')

                # Send response
                await self.send(text_data=json.dumps({
                    'type': 'audio_response',
                    'transcript': gemini_result.get('transcript', ''),
                    'input_transcript': user_transcript,
                    'audio': audio_base64,
                    'voice': voice_name,
                    'user_message_id': str(user_message.id),
                    'assistant_message_id': str(assistant_message.id),
                    'response_time': gemini_result['response_time'],
                    'total_processing_time': processing_time,
                    'model': gemini_result['model'],
                    'success': gemini_result['success']
                }))

        except Exception as e:
            logger.error(f"Audio input processing failed: {e}")
            await self._send_error(f"Audio input processing failed: {str(e)}")

    async def _process_image_data(self, image_data: str) -> tuple[Optional[bytes], Optional[str]]:
        """Validate and process image data"""
        try:
            # Remove data URL prefix if present
            if ',' in image_data:
                header, image_data = image_data.split(',', 1)
                if 'data:' in header and ';' in header:
                    mime_type = header.split('data:')[1].split(';')[0]
                else:
                    mime_type = 'image/jpeg'
            else:
                mime_type = 'image/jpeg'

            # Supported formats
            supported_types = {'image/jpeg', 'image/png', 'image/webp'}
            if mime_type not in supported_types:
                await self._send_error(f"Unsupported image type: {mime_type}")
                return None, None

            # Decode and validate
            image_bytes = base64.b64decode(image_data)

            # Size check (10MB limit)
            if len(image_bytes) > 10 * 1024 * 1024:
                await self._send_error("Image too large (max 10MB)")
                return None, None

            # Validate image
            image = Image.open(io.BytesIO(image_bytes))
            image.verify()

            return image_bytes, mime_type

        except Exception as e:
            await self._send_error(f"Invalid image data: {str(e)}")
            return None, None

    async def _handle_session_info(self):
        """Send session information"""
        try:
            message_count = await self._get_message_count()

            await self.send(text_data=json.dumps({
                'type': 'session_info',
                'session_id': self.session_id,
                'user': self.user_obj.username if self.user_obj else 'Anonymous',
                'message_count': message_count,
                'created_at': self.chat_session.created_at.isoformat(),
                'updated_at': self.chat_session.updated_at.isoformat(),
                'success': True
            }))

        except Exception as e:
            await self._send_error(f"Failed to get session info: {str(e)}")

    async def _handle_history_request(self, data: Dict[str, Any]):
        """Send conversation history"""
        try:
            limit = min(data.get('limit', 50), 100)  # Max 100 messages
            messages = await self._get_recent_messages(limit)

            await self.send(text_data=json.dumps({
                'type': 'history',
                'messages': messages,
                'count': len(messages),
                'success': True
            }))

        except Exception as e:
            await self._send_error(f"Failed to get history: {str(e)}")

    # Optimized async database operations
    async def _get_or_create_session(self):
        """Get or create chat session - optimized async"""
        from django.utils import timezone
        from asgiref.sync import sync_to_async

        # Use direct async database calls
        try:
            session = await sync_to_async(ChatSession.objects.select_related().get)(
                user=self.user_obj,
                is_active=True
            )
            # Update timestamp in background without blocking
            asyncio.create_task(self._update_session_timestamp(session))
            return session
        except ChatSession.DoesNotExist:
            return await sync_to_async(ChatSession.objects.create)(
                user=self.user_obj,
                is_active=True,
                title=f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                metadata={}
            )

    async def _save_message(self, content: str, message_type: str, sender_type: str,
                           metadata=None, processing_time=None):
        """Save message to database - non-blocking"""
        from asgiref.sync import sync_to_async

        # Create message asynchronously
        message = await sync_to_async(ChatMessage.objects.create)(
            session=self.chat_session,
            content=content,
            message_type=message_type,
            sender_type=sender_type,
            metadata=metadata or {},
            processing_time=processing_time
        )
        return message

    async def _update_session_timestamp(self, session):
        """Background session timestamp update"""
        from django.utils import timezone
        from asgiref.sync import sync_to_async

        try:
            await sync_to_async(ChatSession.objects.filter(id=session.id).update)(
                updated_at=timezone.now()
            )
        except Exception:
            pass  # Don't let timestamp updates block the main flow

    async def _get_message_count(self):
        """Get message count for session - cached"""
        from asgiref.sync import sync_to_async
        return await sync_to_async(self.chat_session.messages.count)()

    async def _get_recent_messages(self, limit: int):
        """Get recent messages - optimized query"""
        from asgiref.sync import sync_to_async

        def get_messages():
            messages = self.chat_session.messages.select_related().order_by('-created_at')[:limit]
            return [
                {
                    'id': str(msg.id),
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'sender_type': msg.sender_type,
                    'created_at': msg.created_at.isoformat(),
                    'metadata': msg.metadata,
                    'processing_time': msg.processing_time
                }
                for msg in reversed(messages)
            ]

        return await sync_to_async(get_messages)()

    async def _update_session_activity(self):
        """Update session last activity - non-blocking"""
        if self.chat_session:
            # Run in background without blocking
            asyncio.create_task(self._update_session_timestamp(self.chat_session))

    async def _send_error(self, message: str):
        """Send error response"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'success': False
        }))

    # A2A Integration Methods
    async def _handle_agent_switch(self, data: Dict[str, Any]):
        """Handle agent switching"""
        try:
            new_agent_slug = data.get('agent_slug')
            if not new_agent_slug:
                await self._send_error("Agent slug is required")
                return

            # Validate agent exists
            agent = await self.worker_manager.get_worker(new_agent_slug)
            if not agent:
                await self._send_error(f"Agent '{new_agent_slug}' not found")
                return

            # Switch to new agent
            old_agent = self.current_agent_slug
            self.current_agent_slug = new_agent_slug

            # Initialize discovery service for new agent if needed
            if not self.discovery_service and hasattr(agent, 'llm'):
                self.discovery_service = AgentDiscoveryService(agent.llm)

            logger.info(f"Switched from {old_agent} to {new_agent_slug}")

            await self.send(text_data=json.dumps({
                'type': 'agent_switched',
                'old_agent': old_agent,
                'new_agent': new_agent_slug,
                'agent_name': agent.agent_name,
                'agent_description': agent.agent_description,
                'success': True
            }))

        except Exception as e:
            logger.error(f"Agent switch failed: {e}")
            await self._send_error(f"Failed to switch agent: {str(e)}")

    async def _handle_list_agents(self):
        """Send list of available A2A agents"""
        try:
            # Define available agents with their voice characteristics
            available_agents = {
                "general-worker": {
                    "name": "General Assistant",
                    "description": "General-purpose AI assistant for various tasks",
                    "voice_style": "Warm and helpful",
                    "capabilities": ["text", "conversation", "general_assistance", "worker_coordination"]
                },
                "flight-specialist": {
                    "name": "Flight Specialist",
                    "description": "Specialized agent for flight booking and travel information",
                    "voice_style": "Professional travel expert",
                    "capabilities": ["flight_booking", "travel_info", "airline_data", "route_planning"]
                },
                "hotel-specialist": {
                    "name": "Hotel Specialist",
                    "description": "Specialized agent for hotel booking and accommodation",
                    "voice_style": "Friendly hospitality expert",
                    "capabilities": ["hotel_booking", "accommodation", "hospitality_services"]
                },
                "travel-assistant": {
                    "name": "Travel Assistant",
                    "description": "Comprehensive travel planning and coordination",
                    "voice_style": "Energetic travel coordinator",
                    "capabilities": ["travel_planning", "trip_coordination", "destination_info"]
                }
            }

            await self.send(text_data=json.dumps({
                'type': 'agents_list',
                'current_agent': self.current_agent_slug,
                'agents': available_agents,
                'success': True
            }))

        except Exception as e:
            logger.error(f"List agents failed: {e}")
            await self._send_error(f"Failed to list agents: {str(e)}")

    async def _handle_agent_info(self, data: Dict[str, Any]):
        """Get information about specific agent"""
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
                'capabilities': agent.capabilities,
                'is_current': agent_slug == self.current_agent_slug,
                'success': True
            }))

        except Exception as e:
            logger.error(f"Get agent info failed: {e}")
            await self._send_error(f"Failed to get agent info: {str(e)}")

    async def _process_with_a2a_agent(self, user_input: str, message_type: str, callback=None) -> Dict[str, Any]:
        """Process message through optimized A2A agent system"""
        try:
            # Fast agent retrieval with caching
            agent = await self.worker_manager.get_worker(self.current_agent_slug)
            if not agent:
                return {
                    'success': False,
                    'error': f"Current agent '{self.current_agent_slug}' not available"
                }

            # Parallel initialization of discovery service and delegation check
            async def initialize_discovery():
                if not self.discovery_service and hasattr(agent, 'llm'):
                    self.discovery_service = AgentDiscoveryService(agent.llm)
                return self.discovery_service

            async def check_delegation():
                if self.discovery_service:
                    return await self.discovery_service.should_delegate_request(
                        user_request=user_input,
                        current_agent_slug=self.current_agent_slug
                    )
                return False, None

            # Run initialization and delegation check in parallel
            async def dummy_check():
                return False, None

            discovery_service, (should_delegate, target_agent) = await asyncio.gather(
                initialize_discovery(),
                check_delegation() if self.discovery_service else dummy_check()
            )

            # Fast delegation processing
            if should_delegate and target_agent:
                # Send immediate delegation notification via WebSocket
                await self.send(text_data=json.dumps({
                    'type': 'delegation_in_progress',
                    'target_agent': target_agent,
                    'message': f'Routing to {target_agent} specialist...'
                }))

                # Get specialist agent and process in parallel
                specialist_agent = await self.worker_manager.get_worker(target_agent)
                if specialist_agent:
                    # Start processing immediately
                    specialist_response = await specialist_agent.process_request(
                        user_input=user_input,  # Direct input for faster processing
                        context_id=self.session_id,
                        session_id=self.session_id,
                        user_name=self.user_obj.username if self.user_obj else "user"
                    )

                    # Update current agent (no await needed)
                    old_agent = self.current_agent_slug
                    self.current_agent_slug = target_agent

                    return {
                        'success': True,
                        'response': specialist_response,
                        'agent_switched': True,
                        'old_agent': old_agent,
                        'new_agent': target_agent,
                        'agent_name': specialist_agent.agent_name,
                        'delegation_occurred': True
                    }

            # Direct processing with current agent (no wrapper text)
            response = await agent.process_request(
                user_input=user_input,
                context_id=self.session_id,
                session_id=self.session_id,
                user_name=self.user_obj.username if self.user_obj else "user"
            )

            return {
                'success': True,
                'response': response,
                'agent_switched': False,
                'delegation_occurred': False,
                'current_agent': self.current_agent_slug,
                'agent_name': agent.agent_name
            }

        except Exception as e:
            logger.error(f"A2A processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _handle_start_voice_session(self):
        """Start continuous voice conversation session"""
        try:
            # Import here to avoid circular imports
            from ..services.websocket_live_client import ContinuousVoiceSession
            from django.conf import settings

            # Create websocket callback that sends messages to frontend
            async def websocket_callback(data):
                await self.send(text_data=json.dumps(data))

            # Initialize continuous voice session
            from config.api_config import APIConfig
            api_key = APIConfig.get_api_key('google')
            if not api_key:
                await self.send(text_data=json.dumps({
                    'type': 'voice_session_status',
                    'status': 'error',
                    'message': 'Gemini API key not configured'
                }))
                return

            # Store session for this websocket
            self.voice_session = ContinuousVoiceSession(api_key)

            # Start the session
            await self.voice_session.start(websocket_callback)

            # Send success response
            await self.send(text_data=json.dumps({
                'type': 'voice_session_status',
                'status': 'started',
                'message': 'Continuous voice session started'
            }))

            logger.info("Continuous voice session started successfully")

        except Exception as e:
            logger.error(f"Failed to start voice session: {e}")
            await self.send(text_data=json.dumps({
                'type': 'voice_session_status',
                'status': 'error',
                'message': f'Failed to start session: {str(e)}'
            }))

    async def _handle_stop_voice_session(self):
        """Stop continuous voice conversation session"""
        try:
            if hasattr(self, 'voice_session') and self.voice_session:
                await self.voice_session.stop()
                self.voice_session = None

            await self.send(text_data=json.dumps({
                'type': 'voice_session_status',
                'status': 'stopped',
                'message': 'Continuous voice session stopped'
            }))

            logger.info("Continuous voice session stopped")

        except Exception as e:
            logger.error(f"Failed to stop voice session: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to stop session: {str(e)}'
            }))

    async def _handle_voice_audio_chunk(self, data):
        """Handle incoming audio chunk from user in continuous mode"""
        try:
            if not hasattr(self, 'voice_session') or not self.voice_session:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'No active voice session'
                }))
                return

            audio_data = data.get('audio')
            if not audio_data:
                logger.warning("Received empty audio data")
                return

            # Decode base64 audio data
            try:
                audio_bytes = base64.b64decode(audio_data)
                logger.debug(f"Received audio chunk: {len(audio_bytes)} bytes")

                # Skip if too small or too large
                if len(audio_bytes) < 100:  # Skip very small chunks
                    logger.debug("Skipping small audio chunk")
                    return

                if len(audio_bytes) > 50000:  # Skip very large chunks
                    logger.debug("Skipping large audio chunk")
                    return

                # Process audio through continuous voice session
                # Send base64 string to Live API client (it will decode it there)
                await self.voice_session.process_audio(audio_data)

            except Exception as decode_error:
                logger.error(f"Failed to decode audio data: {decode_error}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid audio data format'
                }))

        except Exception as e:
            logger.error(f"Failed to process voice audio chunk: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Audio processing failed: {str(e)}'
            }))