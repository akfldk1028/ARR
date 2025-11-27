"""
Optimized Gemini Live API WebSocket Consumer
High-performance implementation with advanced features
"""

import base64
import logging
import time
from typing import Dict, Any, Optional
from PIL import Image
import io

from .base import BaseOptimizedConsumer
from ..services.service_manager import get_gemini_service


logger = logging.getLogger(__name__)


class GeminiLiveConsumer(BaseOptimizedConsumer):
    """
    Optimized WebSocket consumer for Gemini Live API with:
    - Connection pooling
    - Session management
    - Advanced error handling
    - Performance monitoring
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gemini_service = None
        self.session_id: Optional[str] = None
        self.max_image_size = 10 * 1024 * 1024  # 10MB
        self.supported_image_types = {'image/jpeg', 'image/png', 'image/webp'}

    async def connect(self):
        """Enhanced connection with service initialization"""
        try:
            # Initialize Gemini service
            self.gemini_service = get_gemini_service()

            # Generate session ID for this connection
            self.session_id = f"session_{self.connection_id}"

            # Call parent connect
            await super().connect()

            # Send welcome message
            await self.send_success({
                'message': 'Connected to Gemini Live API',
                'capabilities': ['text', 'image', 'audio', 'video'],
                'session_id': self.session_id,
                'rate_limits': {
                    'max_messages_per_minute': self.max_messages_per_window,
                    'max_image_size_mb': self.max_image_size // (1024 * 1024)
                }
            })

        except Exception as e:
            logger.error(f"Gemini consumer connection failed: {e}")
            await self.send_error(f"Service initialization failed: {str(e)}")
            await self.close()

    async def _process_message(self, message_data: Dict[str, Any]):
        """Process different message types"""
        message_type = message_data.get('type')
        start_time = time.time()

        try:
            if message_type == 'text':
                await self._handle_text_message(message_data, start_time)
            elif message_type == 'image':
                await self._handle_image_message(message_data, start_time)
            elif message_type == 'audio':
                await self._handle_audio_message(message_data, start_time)
            elif message_type == 'video':
                await self._handle_video_message(message_data, start_time)
            elif message_type == 'health_check':
                await self._handle_health_check(start_time)
            elif message_type == 'stats':
                await self._handle_stats_request()
            else:
                await self.send_error(f"Unsupported message type: {message_type}")

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Message processing failed for {message_type}: {e}")

            await self.send_error(
                f"Processing failed: {str(e)}",
                error_code=f"{message_type.upper()}_PROCESSING_ERROR"
            )

            # Log to database for monitoring
            await self._log_message_to_db(message_type, str(e), processing_time)

    async def _handle_text_message(self, message_data: Dict[str, Any], start_time: float):
        """Handle text message processing"""
        user_message = message_data.get('message', '').strip()

        if not user_message:
            await self.send_error("Empty message content", "EMPTY_MESSAGE")
            return

        if len(user_message) > 10000:  # 10K character limit
            await self.send_error("Message too long (max 10,000 characters)", "MESSAGE_TOO_LONG")
            return

        logger.debug(f"Processing text: {user_message[:100]}...")

        # Process with Gemini service
        result = await self.gemini_service.process_text(user_message, self.session_id)

        processing_time = time.time() - start_time

        await self.send_success({
            'message': result['text'],
            'response_time': result['response_time'],
            'processing_time': processing_time,
            'model': result['model'],
            'analysis_type': result['type'],
            'session_id': result.get('session_id', self.session_id)
        })

        # Log successful processing
        await self._log_message_to_db('text', user_message, processing_time)

    async def _handle_image_message(self, message_data: Dict[str, Any], start_time: float):
        """Handle image processing with validation"""
        image_data = message_data.get('image', '')
        prompt = message_data.get('prompt', 'What do you see in this image?')

        if not image_data:
            await self.send_error("No image data provided", "NO_IMAGE_DATA")
            return

        if len(prompt) > 1000:
            await self.send_error("Prompt too long (max 1,000 characters)", "PROMPT_TOO_LONG")
            return

        try:
            # Validate and process image
            image_bytes, mime_type = await self._process_image_data(image_data)

            if not image_bytes:
                return  # Error already sent

            logger.debug(f"Processing image ({len(image_bytes)} bytes) with prompt: {prompt[:50]}...")

            # Process with Gemini service
            result = await self.gemini_service.process_image(image_bytes, prompt, mime_type)

            processing_time = time.time() - start_time

            await self.send_success({
                'message': result['text'],
                'response_time': result['response_time'],
                'processing_time': processing_time,
                'model': result['model'],
                'analysis_type': result['type'],
                'image_info': {
                    'size_bytes': len(image_bytes),
                    'mime_type': mime_type
                }
            })

            # Log successful processing
            await self._log_message_to_db('image', f"Image analysis: {prompt}", processing_time)

        except Exception as e:
            logger.error(f"Image processing error: {e}")
            await self.send_error(f"Image processing failed: {str(e)}", "IMAGE_PROCESSING_ERROR")

    async def _process_image_data(self, image_data: str) -> tuple[Optional[bytes], Optional[str]]:
        """Process and validate image data"""
        try:
            # Remove data URL prefix if present
            if ',' in image_data:
                header, image_data = image_data.split(',', 1)

                # Extract MIME type from header
                if 'data:' in header and ';' in header:
                    mime_type = header.split('data:')[1].split(';')[0]
                else:
                    mime_type = 'image/jpeg'  # Default
            else:
                mime_type = 'image/jpeg'  # Default

            # Validate MIME type
            if mime_type not in self.supported_image_types:
                await self.send_error(
                    f"Unsupported image type: {mime_type}. Supported: {', '.join(self.supported_image_types)}",
                    "UNSUPPORTED_IMAGE_TYPE"
                )
                return None, None

            # Decode base64
            image_bytes = base64.b64decode(image_data)

            # Check file size
            if len(image_bytes) > self.max_image_size:
                await self.send_error(
                    f"Image too large: {len(image_bytes)} bytes (max: {self.max_image_size})",
                    "IMAGE_TOO_LARGE"
                )
                return None, None

            # Validate image format
            try:
                image = Image.open(io.BytesIO(image_bytes))
                image.verify()  # Verify it's a valid image

                logger.debug(f"Validated image: {image.width}x{image.height} pixels, {image.format}")

            except Exception as e:
                await self.send_error(f"Invalid image format: {str(e)}", "INVALID_IMAGE_FORMAT")
                return None, None

            return image_bytes, mime_type

        except Exception as e:
            await self.send_error(f"Image data processing failed: {str(e)}", "IMAGE_DATA_ERROR")
            return None, None

    async def _handle_audio_message(self, message_data: Dict[str, Any], start_time: float):
        """Handle audio processing (placeholder for future implementation)"""
        audio_data = message_data.get('audio', '')

        if not audio_data:
            await self.send_error("No audio data provided", "NO_AUDIO_DATA")
            return

        processing_time = time.time() - start_time

        # Placeholder response
        await self.send_success({
            'message': "Audio processing is not yet fully implemented. Coming soon with Live API audio support!",
            'response_time': 0,
            'processing_time': processing_time,
            'model': 'placeholder',
            'analysis_type': 'audio_placeholder',
            'audio_info': {
                'size_bytes': len(audio_data)
            }
        })

    async def _handle_video_message(self, message_data: Dict[str, Any], start_time: float):
        """Handle video processing (placeholder for future implementation)"""
        frames = message_data.get('frames', [])
        prompt = message_data.get('prompt', 'What is happening in this video?')

        if not frames:
            await self.send_error("No video frames provided", "NO_VIDEO_FRAMES")
            return

        processing_time = time.time() - start_time

        # Placeholder response
        await self.send_success({
            'message': "Video processing is not yet fully implemented. Coming soon with Live API video support!",
            'response_time': 0,
            'processing_time': processing_time,
            'model': 'placeholder',
            'analysis_type': 'video_placeholder',
            'video_info': {
                'frame_count': len(frames)
            }
        })

    async def _handle_health_check(self, start_time: float):
        """Handle health check request"""
        try:
            health_result = await self.gemini_service.health_check()
            processing_time = time.time() - start_time

            await self.send_success({
                'message': 'Service health check completed',
                'health_status': health_result,
                'processing_time': processing_time,
                'connection_stats': await self.get_connection_stats()
            })

        except Exception as e:
            await self.send_error(f"Health check failed: {str(e)}", "HEALTH_CHECK_ERROR")

    async def _handle_stats_request(self):
        """Handle connection statistics request"""
        stats = await self.get_connection_stats()

        await self.send_success({
            'message': 'Connection statistics',
            'stats': stats,
            'service_info': {
                'session_id': self.session_id,
                'rate_limits': {
                    'messages_per_window': self.max_messages_per_window,
                    'window_seconds': self.rate_limit_window
                }
            }
        })