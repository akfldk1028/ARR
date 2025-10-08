"""
Base WebSocket Consumer with optimization features
Based on Django Channels best practices for 2025
"""

import json
import logging
import time
import asyncio
from typing import Dict, Any, Optional
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import StopConsumer
from django.core.cache import cache
from django.db import transaction
from channels.db import database_sync_to_async


logger = logging.getLogger(__name__)


class BaseOptimizedConsumer(AsyncWebsocketConsumer):
    """
    Base consumer with optimization features:
    - Connection management
    - Rate limiting per connection
    - Error handling
    - Monitoring and logging
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.connected_at: Optional[float] = None
        self.last_activity: Optional[float] = None
        self.message_count: int = 0
        self.rate_limit_window: int = 60  # 1 minute
        self.max_messages_per_window: int = 100

    async def connect(self):
        """Enhanced connection handling"""
        try:
            # Generate connection ID
            self.connection_id = f"conn_{int(time.time() * 1000)}"
            self.connected_at = time.time()
            self.last_activity = self.connected_at

            # Get user if authenticated
            if self.scope.get("user") and self.scope["user"].is_authenticated:
                self.user_id = str(self.scope["user"].id)

            # Accept connection
            await self.accept()

            # Track connection
            await self._track_connection()

            logger.info(f"WebSocket connected: {self.connection_id} (user: {self.user_id})")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            await self.close()

    async def disconnect(self, close_code):
        """Enhanced disconnection handling"""
        try:
            # Cleanup operations
            await self._cleanup_connection()

            connection_duration = (
                time.time() - self.connected_at
                if self.connected_at else 0
            )

            logger.info(
                f"WebSocket disconnected: {self.connection_id} "
                f"(duration: {connection_duration:.2f}s, messages: {self.message_count})"
            )

        except Exception as e:
            logger.error(f"Disconnect cleanup failed: {e}")
        finally:
            # Always raise StopConsumer to clean up properly
            raise StopConsumer()

    async def receive(self, text_data):
        """Enhanced message handling with rate limiting"""
        try:
            # Update activity tracking
            self.last_activity = time.time()
            self.message_count += 1

            # Rate limiting check
            if not await self._check_rate_limit():
                await self.send_error("Rate limit exceeded. Please slow down.")
                return

            # Parse message
            try:
                message_data = json.loads(text_data)
            except json.JSONDecodeError as e:
                await self.send_error(f"Invalid JSON: {str(e)}")
                return

            # Validate message
            if not await self._validate_message(message_data):
                return

            # Process message
            await self._process_message(message_data)

        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await self.send_error("Internal server error")

    async def _track_connection(self):
        """Track connection for monitoring"""
        cache_key = f"ws_connection:{self.connection_id}"
        connection_data = {
            'connected_at': self.connected_at,
            'user_id': self.user_id,
            'message_count': 0
        }
        cache.set(cache_key, connection_data, timeout=3600)  # 1 hour

    async def _cleanup_connection(self):
        """Cleanup connection resources"""
        if self.connection_id:
            cache_key = f"ws_connection:{self.connection_id}"
            cache.delete(cache_key)

            # Clear rate limiting cache
            rate_limit_key = f"rate_limit:{self.connection_id}"
            cache.delete(rate_limit_key)

    async def _check_rate_limit(self) -> bool:
        """Check if connection is within rate limits"""
        if not self.connection_id:
            return True

        rate_limit_key = f"rate_limit:{self.connection_id}"
        current_time = int(time.time())
        window_start = current_time - self.rate_limit_window

        # Get current window messages
        messages_in_window = cache.get(rate_limit_key, [])

        # Filter to current window
        messages_in_window = [
            timestamp for timestamp in messages_in_window
            if timestamp > window_start
        ]

        # Check limit
        if len(messages_in_window) >= self.max_messages_per_window:
            return False

        # Add current message
        messages_in_window.append(current_time)
        cache.set(rate_limit_key, messages_in_window, timeout=self.rate_limit_window)

        return True

    async def _validate_message(self, message_data: Dict[str, Any]) -> bool:
        """Validate incoming message"""
        if not isinstance(message_data, dict):
            await self.send_error("Message must be a JSON object")
            return False

        if 'type' not in message_data:
            await self.send_error("Message must have a 'type' field")
            return False

        return True

    async def _process_message(self, message_data: Dict[str, Any]):
        """Process incoming message - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement _process_message")

    async def send_response(self, response_data: Dict[str, Any]):
        """Send structured response"""
        try:
            await self.send(text_data=json.dumps({
                **response_data,
                'timestamp': time.time(),
                'connection_id': self.connection_id
            }))
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    async def send_error(self, error_message: str, error_code: str = "GENERAL_ERROR"):
        """Send error response"""
        await self.send_response({
            'type': 'error',
            'error_code': error_code,
            'message': error_message,
            'success': False
        })

    async def send_success(self, data: Dict[str, Any]):
        """Send success response"""
        await self.send_response({
            'type': 'response',
            'success': True,
            **data
        })

    @database_sync_to_async
    def _log_message_to_db(self, message_type: str, content: str, response_time: float):
        """Log message to database (async database operation)"""
        # This would be implemented based on your logging model
        # Example:
        # MessageLog.objects.create(
        #     connection_id=self.connection_id,
        #     user_id=self.user_id,
        #     message_type=message_type,
        #     content=content[:1000],  # Truncate for storage
        #     response_time=response_time
        # )
        pass

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        if not self.connected_at:
            return {}

        return {
            'connection_id': self.connection_id,
            'user_id': self.user_id,
            'connected_at': self.connected_at,
            'duration': time.time() - self.connected_at,
            'message_count': self.message_count,
            'last_activity': self.last_activity
        }