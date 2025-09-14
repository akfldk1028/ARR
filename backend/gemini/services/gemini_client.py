"""
Optimized Gemini Live API Client with Connection Pool Management
Based on Google AI best practices for 2025
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from google import genai
from google.genai import types


logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategies for different error types"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


@dataclass
class ClientConfig:
    """Configuration for Gemini client"""
    api_key: str
    model: str = "models/gemini-2.0-flash-exp"
    max_connections: int = 5
    connection_timeout: int = 30
    request_timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_per_minute: int = 60
    enable_compression: bool = True
    session_ttl: int = 900  # 15 minutes for audio sessions


class ConnectionPool:
    """Manage Gemini API connections with pooling and reuse"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self.active_sessions: Dict[str, Any] = {}
        self.session_created: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def get_client(self) -> genai.Client:
        """Get or create a Gemini client instance"""
        return genai.Client(api_key=self.config.api_key)

    async def create_session(self, session_id: str, config: types.LiveConnectConfig) -> Any:
        """Create or reuse a Live API session"""
        async with self._lock:
            now = time.time()

            # Clean up expired sessions
            await self._cleanup_expired_sessions(now)

            # Check if we have an active session
            if session_id in self.active_sessions:
                session_age = now - self.session_created[session_id]
                if session_age < self.config.session_ttl:
                    logger.debug(f"Reusing existing session {session_id}")
                    return self.active_sessions[session_id]
                else:
                    logger.debug(f"Session {session_id} expired, creating new one")
                    await self._close_session(session_id)

            # Create new session - connect() returns a context manager
            client = await self.get_client()
            session = client.aio.live.connect(
                model=self.config.model,
                config=config
            )

            self.active_sessions[session_id] = session
            self.session_created[session_id] = now

            logger.info(f"Created new Live API session {session_id}")
            return session

    async def _cleanup_expired_sessions(self, current_time: float):
        """Remove expired sessions"""
        expired_sessions = [
            sid for sid, created_time in self.session_created.items()
            if current_time - created_time > self.config.session_ttl
        ]

        for session_id in expired_sessions:
            await self._close_session(session_id)

    async def _close_session(self, session_id: str):
        """Close and remove a session"""
        if session_id in self.active_sessions:
            try:
                session = self.active_sessions[session_id]
                await session.close()
            except Exception as e:
                logger.warning(f"Error closing session {session_id}: {e}")

            del self.active_sessions[session_id]
            del self.session_created[session_id]

    async def cleanup_all(self):
        """Close all active sessions"""
        async with self._lock:
            for session_id in list(self.active_sessions.keys()):
                await self._close_session(session_id)


class RateLimiter:
    """Rate limiting for API requests"""

    def __init__(self, max_requests_per_minute: int = 60):
        self.max_requests = max_requests_per_minute
        self.requests_timestamps = []
        self._lock = asyncio.Lock()

    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        async with self._lock:
            now = time.time()

            # Remove timestamps older than 1 minute
            self.requests_timestamps = [
                ts for ts in self.requests_timestamps
                if now - ts < 60
            ]

            if len(self.requests_timestamps) >= self.max_requests:
                # Calculate wait time
                oldest_request = min(self.requests_timestamps)
                wait_time = 60 - (now - oldest_request)
                if wait_time > 0:
                    logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)

            self.requests_timestamps.append(now)


class ErrorHandler:
    """Handle various Gemini API errors with retry logic"""

    @staticmethod
    async def handle_with_retry(
        func,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    ):
        """Execute function with retry logic"""

        for attempt in range(max_retries + 1):
            try:
                return await func()

            except Exception as e:
                error_code = getattr(e, 'code', None)
                error_message = str(e).lower()

                # Determine if we should retry
                should_retry = (
                    attempt < max_retries and (
                        error_code in [503, 504] or  # Service unavailable, timeout
                        'overloaded' in error_message or
                        'deadline exceeded' in error_message or
                        'timeout' in error_message
                    )
                )

                if not should_retry:
                    logger.error(f"Non-retryable error or max retries reached: {e}")
                    raise

                # Calculate delay
                if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                    delay = retry_delay * (2 ** attempt)
                else:
                    delay = retry_delay

                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

        raise Exception(f"Max retries ({max_retries}) exceeded")


class OptimizedGeminiClient:
    """High-performance Gemini Live API client with advanced features"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self.connection_pool = ConnectionPool(config)
        self.rate_limiter = RateLimiter(config.rate_limit_per_minute)
        self.error_handler = ErrorHandler()

        # Live API configuration
        self.live_config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            temperature=0.9,
            max_output_tokens=2048,
            system_instruction="""You are a helpful AI assistant with multimodal capabilities.
            You can analyze images, video streams, and have natural conversations.
            Provide detailed and helpful responses. Be concise yet informative."""
        )

        logger.info(f"Initialized Gemini client with model: {config.model}")

    async def process_text_stream(
        self,
        message: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process text with optimized streaming"""

        session_id = session_id or f"text_{int(time.time())}"
        start_time = time.time()

        async def _process():
            await self.rate_limiter.wait_if_needed()

            # Create a new session directly (no pooling for now)
            client = await self.connection_pool.get_client()

            # Use the session as async context manager directly
            async with client.aio.live.connect(
                model=self.config.model,
                config=self.live_config
            ) as session:
                # Send message with correct turns structure
                await session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [{"text": message}]
                    },
                    turn_complete=True
                )

                # Collect response
                full_response = ""
                async for response in session.receive():
                    if hasattr(response, 'text') and response.text:
                        full_response += response.text
                    elif hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'model_turn') and response.server_content.model_turn:
                            model_turn = response.server_content.model_turn
                            if hasattr(model_turn, 'parts') and model_turn.parts:
                                for part in model_turn.parts:
                                    if hasattr(part, 'text') and part.text:
                                        full_response += part.text

                        if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                            break

                return full_response

        try:
            response_text = await self.error_handler.handle_with_retry(
                _process,
                self.config.max_retries,
                self.config.retry_delay
            )

            response_time = time.time() - start_time

            return {
                'text': response_text or "No response received",
                'response_time': response_time,
                'model': self.config.model,
                'type': 'text_stream_optimized',
                'success': bool(response_text),
                'session_id': session_id
            }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Text processing failed: {e}")

            return {
                'text': f"Processing error: {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': 'error',
                'success': False,
                'session_id': session_id
            }

    async def process_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg"
    ) -> Dict[str, Any]:
        """Process image with error handling and rate limiting"""

        start_time = time.time()

        async def _process():
            await self.rate_limiter.wait_if_needed()

            client = await self.connection_pool.get_client()

            response = await client.aio.models.generate_content(
                model=self.config.model,
                contents=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                ]
            )

            return response.text

        try:
            response_text = await self.error_handler.handle_with_retry(
                _process,
                self.config.max_retries,
                self.config.retry_delay
            )

            response_time = time.time() - start_time

            return {
                'text': response_text or "No image analysis response",
                'response_time': response_time,
                'model': f"{self.config.model} (image)",
                'type': 'image_optimized',
                'success': bool(response_text)
            }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Image processing failed: {e}")

            return {
                'text': f"Image processing error: {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': 'error',
                'success': False
            }

    async def health_check(self) -> Dict[str, Any]:
        """Check service health and connectivity"""
        start_time = time.time()

        try:
            client = await self.connection_pool.get_client()

            # Simple test request
            response = await client.aio.models.generate_content(
                model=self.config.model,
                contents="Health check"
            )

            response_time = time.time() - start_time

            return {
                'status': 'healthy',
                'model': self.config.model,
                'response_time': response_time,
                'active_sessions': len(self.connection_pool.active_sessions),
                'success': True
            }

        except Exception as e:
            response_time = time.time() - start_time

            return {
                'status': 'unhealthy',
                'error': str(e),
                'response_time': response_time,
                'success': False
            }

    async def cleanup(self):
        """Clean up resources"""
        await self.connection_pool.cleanup_all()
        logger.info("Gemini client cleanup completed")