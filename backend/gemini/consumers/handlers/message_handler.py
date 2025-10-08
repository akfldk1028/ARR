"""
Message Handler - General message processing (text, audio, image)
"""

import asyncio
import base64
import json
import logging
import time
from typing import Dict, Any
from PIL import Image
import io
from asgiref.sync import sync_to_async

from .utils import safe_log_text, format_error_message

logger = logging.getLogger('gemini.consumers')


class MessageHandler:
    """Handle general text, audio, and image messages"""

    def __init__(self, consumer):
        self.consumer = consumer
        self.websocket_send = consumer.send
        self.session_id = consumer.browser_session_id
        self.user_obj = consumer.user_obj
        self.chat_session = consumer.chat_session
        self.gemini_service = consumer.gemini_service

    async def handle_text(self, data):
        """Handle text messages"""
        content = data.get('message', '').strip()
        if not content or len(content) > 10000:
            await self._send_error("Invalid message content")
            return

        try:
            # Save user message
            user_message = await self._save_user_message(content, 'text')
            user_message_id = str(user_message.id)

            # Send immediate acknowledgment
            await self.websocket_send(text_data=json.dumps({
                'type': 'message_received',
                'message_id': user_message_id,
                'timestamp': time.time()
            }))

            # Process with current agent
            agent = await self.consumer.worker_manager.get_worker(self.consumer.current_agent_slug)
            if not agent:
                await self._send_error(f"Agent {self.consumer.current_agent_slug} not available")
                return

            response = await agent.process_request(
                user_input=content,
                context_id=self.session_id,
                session_id=self.session_id,
                user_name=self.user_obj.username if self.user_obj else "user"
            )

            # Save and send response
            ai_message = await self._save_ai_message(response, 'text')
            await self.websocket_send(text_data=json.dumps({
                'type': 'message',
                'content': response,
                'message_id': str(ai_message.id),
                'agent': self.consumer.current_agent_slug,
                'timestamp': time.time()
            }))

        except Exception as e:
            logger.error(f"Text processing error: {e}")
            await self._send_error(f"처리 실패: {str(e)}")

    async def handle_text_audio(self, data):
        """Handle text + audio messages"""
        try:
            content = data.get('message', '').strip()
            audio_data = data.get('audio', '')

            if not content and not audio_data:
                await self._send_error("No content provided")
                return

            # Process text if available
            if content:
                await self.handle_text(data)

            # Process audio if available
            if audio_data:
                await self.handle_audio(data)

        except Exception as e:
            logger.error(f"Text+Audio processing error: {e}")
            await self._send_error(f"복합 메시지 처리 실패: {str(e)}")

    async def handle_audio(self, data):
        """Handle audio messages"""
        try:
            audio_data = data.get('audio')
            if not audio_data:
                await self._send_error("No audio data provided")
                return

            # Validate audio data
            try:
                audio_bytes = base64.b64decode(audio_data)
                if len(audio_bytes) < 100 or len(audio_bytes) > 10000000:  # 10MB limit
                    await self._send_error("Invalid audio size")
                    return
            except Exception:
                await self._send_error("Invalid audio format")
                return

            # Send processing status
            await self.websocket_send(text_data=json.dumps({
                'type': 'processing_status',
                'status': 'processing_audio',
                'message': '음성을 처리하는 중...'
            }))

            # Process with Gemini
            response = await self.gemini_service.process_audio_message(
                audio_data=audio_data,
                session_id=self.session_id
            )

            if response.get('success'):
                transcribed_text = response.get('transcribed_text', '')
                ai_response = response.get('response', '')

                # Save messages
                if transcribed_text:
                    user_message = await self._save_user_message(transcribed_text, 'audio')
                if ai_response:
                    ai_message = await self._save_ai_message(ai_response, 'text')

                # Send response
                await self.websocket_send(text_data=json.dumps({
                    'type': 'audio_response',
                    'transcribed_text': transcribed_text,
                    'response': ai_response,
                    'timestamp': time.time()
                }))
            else:
                await self._send_error(f"음성 처리 실패: {response.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            await self._send_error(f"음성 처리 실패: {str(e)}")

    async def handle_image(self, data):
        """Handle image messages"""
        try:
            image_data = data.get('image')
            message = data.get('message', '')

            if not image_data:
                await self._send_error("No image data provided")
                return

            # Validate and process image
            try:
                # Decode base64 image
                image_bytes = base64.b64decode(image_data.split(',')[1] if ',' in image_data else image_data)

                # Validate image size (max 5MB)
                if len(image_bytes) > 5000000:
                    await self._send_error("Image too large (max 5MB)")
                    return

                # Validate image format
                image = Image.open(io.BytesIO(image_bytes))
                if image.format.lower() not in ['jpeg', 'jpg', 'png', 'gif', 'webp']:
                    await self._send_error("Unsupported image format")
                    return

            except Exception:
                await self._send_error("Invalid image format")
                return

            # Send processing status
            await self.websocket_send(text_data=json.dumps({
                'type': 'processing_status',
                'status': 'processing_image',
                'message': '이미지를 분석하는 중...'
            }))

            # Process with Gemini
            response = await self.gemini_service.process_image_message(
                image_data=image_data,
                text_prompt=message,
                session_id=self.session_id
            )

            if response.get('success'):
                ai_response = response.get('response', '')

                # Save messages
                user_message = await self._save_user_message(message or "[이미지]", 'image')
                ai_message = await self._save_ai_message(ai_response, 'text')

                # Send response
                await self.websocket_send(text_data=json.dumps({
                    'type': 'image_response',
                    'response': ai_response,
                    'message_id': str(ai_message.id),
                    'timestamp': time.time()
                }))
            else:
                await self._send_error(f"이미지 처리 실패: {response.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Image processing error: {e}")
            await self._send_error(f"이미지 처리 실패: {str(e)}")

    async def handle_session_info(self, data):
        """Handle session information requests"""
        try:
            session_info = {
                'session_id': self.session_id,
                'current_agent': self.consumer.current_agent_slug,
                'user': self.user_obj.username if self.user_obj else "anonymous",
                'timestamp': time.time()
            }

            await self.websocket_send(text_data=json.dumps({
                'type': 'session_info',
                'session_info': session_info
            }))

        except Exception as e:
            logger.error(f"Session info error: {e}")
            await self._send_error(f"세션 정보 조회 실패: {str(e)}")

    async def handle_history(self, data):
        """Handle chat history requests"""
        try:
            limit = data.get('limit', 50)
            offset = data.get('offset', 0)

            from ...models import ChatMessage

            # Get recent messages
            messages = await sync_to_async(list)(
                ChatMessage.objects.filter(
                    session=self.chat_session
                ).order_by('-created_at')[offset:offset + limit]
            )

            # Format messages
            formatted_messages = []
            for msg in reversed(messages):  # Reverse to get chronological order
                formatted_messages.append({
                    'id': str(msg.id),
                    'role': msg.role,
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'timestamp': msg.created_at.timestamp(),
                    'agent': getattr(msg, 'agent', 'unknown')
                })

            await self.websocket_send(text_data=json.dumps({
                'type': 'chat_history',
                'messages': formatted_messages,
                'total_count': len(formatted_messages)
            }))

        except Exception as e:
            logger.error(f"History retrieval error: {e}")
            await self._send_error(f"대화 기록 조회 실패: {str(e)}")

    async def _save_user_message(self, content: str, message_type: str = 'text'):
        """Save user message to database"""
        from ...models import ChatMessage

        return await sync_to_async(ChatMessage.objects.create)(
            session=self.chat_session,
            role='user',
            content=content,
            message_type=message_type
        )

    async def _save_ai_message(self, content: str, message_type: str = 'text'):
        """Save AI message to database"""
        from ...models import ChatMessage

        return await sync_to_async(ChatMessage.objects.create)(
            session=self.chat_session,
            role='assistant',
            content=content,
            message_type=message_type
        )

    async def _send_error(self, message: str):
        """Send error message to frontend"""
        await self.websocket_send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': time.time()
        }))