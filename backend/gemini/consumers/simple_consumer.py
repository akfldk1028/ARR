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

    async def connect(self):
        """Initialize connection and session"""
        try:
            # Get user if authenticated
            user = self.scope.get("user")
            if user and user.is_authenticated:
                self.user_obj = user
            else:
                self.user_obj = None

            # Initialize Gemini service
            self.gemini_service = get_gemini_service()

            # Create or get session
            self.chat_session = await self._get_or_create_session()
            self.session_id = str(self.chat_session.id)

            # Accept connection
            await self.accept()

            # Send welcome message with safe model access
            try:
                model_name = self.gemini_service.client.config.model
            except Exception as e:
                logger.warning(f"Could not get model name: {e}")
                model_name = "models/gemini-2.0-flash-exp"  # fallback

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
        """Handle incoming messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'text':
                await self._handle_text_message(data)
            elif message_type == 'image':
                await self._handle_image_message(data)
            elif message_type == 'session_info':
                await self._handle_session_info()
            elif message_type == 'history':
                await self._handle_history_request(data)
            else:
                await self._send_error(f"Unsupported message type: {message_type}")

        except json.JSONDecodeError:
            await self._send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await self._send_error(f"Processing error: {str(e)}")

    async def _handle_text_message(self, data: Dict[str, Any]):
        """Handle text message processing"""
        content = data.get('message', '').strip()

        if not content:
            await self._send_error("Empty message content")
            return

        if len(content) > 10000:  # 10K character limit
            await self._send_error("Message too long (max 10,000 characters)")
            return

        start_time = time.time()

        try:
            # Save user message
            user_message = await self._save_message(content, 'text', 'user')

            # Process with Gemini
            result = await self.gemini_service.process_text(content, self.session_id)

            # Save assistant response
            assistant_message = await self._save_message(
                result['text'], 'text', 'assistant',
                metadata={
                    'response_time': result['response_time'],
                    'model': result['model'],
                    'processing_type': result['type']
                },
                processing_time=result['response_time']
            )

            processing_time = time.time() - start_time

            # Send response
            await self.send(text_data=json.dumps({
                'type': 'response',
                'message': result['text'],
                'user_message_id': str(user_message.id),
                'assistant_message_id': str(assistant_message.id),
                'response_time': result['response_time'],
                'total_processing_time': processing_time,
                'model': result['model'],
                'success': True
            }))

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

    # Database operations
    @database_sync_to_async
    def _get_or_create_session(self):
        """Get or create chat session"""
        from django.utils import timezone

        session, created = ChatSession.objects.get_or_create(
            user=self.user_obj,
            is_active=True,
            defaults={
                'title': f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                'metadata': {}
            }
        )

        if not created:
            # Update last activity
            session.updated_at = timezone.now()
            session.save(update_fields=['updated_at'])

        return session

    @database_sync_to_async
    def _save_message(self, content: str, message_type: str, sender_type: str,
                     metadata=None, processing_time=None):
        """Save message to database"""
        return ChatMessage.objects.create(
            session=self.chat_session,
            content=content,
            message_type=message_type,
            sender_type=sender_type,
            metadata=metadata or {},
            processing_time=processing_time
        )

    @database_sync_to_async
    def _get_message_count(self):
        """Get message count for session"""
        return self.chat_session.messages.count()

    @database_sync_to_async
    def _get_recent_messages(self, limit: int):
        """Get recent messages"""
        messages = self.chat_session.messages.order_by('-created_at')[:limit]

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
            for msg in reversed(messages)  # Oldest first
        ]

    @database_sync_to_async
    def _update_session_activity(self):
        """Update session last activity"""
        from django.utils import timezone

        if self.chat_session:
            self.chat_session.updated_at = timezone.now()
            self.chat_session.save(update_fields=['updated_at'])

    async def _send_error(self, message: str):
        """Send error response"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'success': False
        }))