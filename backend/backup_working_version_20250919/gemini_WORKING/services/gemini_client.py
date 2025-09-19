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

# Import centralized configuration
from config.agent_config import AgentConfig, GeminiConfig, VoiceConfig
from config.api_config import APIConfig


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

        # Get centralized configuration
        gemini_config = AgentConfig.get_gemini_config()

        # Live API configuration for TEXT
        self.live_config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            temperature=gemini_config.temperature,
            max_output_tokens=gemini_config.max_output_tokens,
            system_instruction=gemini_config.text_instruction
        )

        # Live API configuration for AUDIO (TTS)
        self.audio_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            temperature=gemini_config.temperature,
            max_output_tokens=gemini_config.max_output_tokens,
            system_instruction=gemini_config.audio_instruction,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=gemini_config.default_voice
                    )
                )
            )
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
                'model': self.config.model,
                'type': 'text_stream_error',
                'success': False,
                'session_id': session_id
            }

    async def process_text_stream_with_callback(
        self,
        message: str,
        session_id: Optional[str] = None,
        callback=None
    ) -> Dict[str, Any]:
        """Process text with Live API streaming and real-time callback"""

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

                # Stream response in real-time with callback
                full_response = ""
                chunk_count = 0
                async for response in session.receive():
                    current_chunk = ""

                    if hasattr(response, 'text') and response.text:
                        current_chunk = response.text
                    elif hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'model_turn') and response.server_content.model_turn:
                            model_turn = response.server_content.model_turn
                            if hasattr(model_turn, 'parts') and model_turn.parts:
                                for part in model_turn.parts:
                                    if hasattr(part, 'text') and part.text:
                                        current_chunk += part.text

                    # Send chunk immediately if we have content and a callback
                    if current_chunk and callback:
                        chunk_count += 1
                        await callback({
                            'chunk': current_chunk,
                            'chunk_id': chunk_count,
                            'session_id': session_id,
                            'is_final': False
                        })

                    full_response += current_chunk

                    # Check for completion
                    if hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                            # Send final callback
                            if callback:
                                await callback({
                                    'chunk': '',
                                    'chunk_id': chunk_count + 1,
                                    'session_id': session_id,
                                    'is_final': True
                                })
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
                'type': 'text_stream_callback',
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

    async def process_text_with_audio(
        self,
        message: str,
        voice_name: str = "Aoede",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process text and return audio response (TTS)"""

        session_id = session_id or f"audio_{int(time.time())}"
        start_time = time.time()

        async def _process():
            await self.rate_limiter.wait_if_needed()

            # Get voice config from centralized configuration
            gemini_config = AgentConfig.get_gemini_config()
            voice_config = AgentConfig.get_voice_config(voice_name)

            # Create audio config with selected voice
            audio_config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                temperature=gemini_config.temperature,
                system_instruction=gemini_config.audio_instruction,
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_config.name
                        )
                    )
                )
            )

            # Create a new session with audio config
            client = await self.connection_pool.get_client()

            async with client.aio.live.connect(
                model=self.config.model,
                config=audio_config
            ) as session:
                # Send message with correct Live API format
                await session.send_client_content(
                    turns=[{
                        "role": "user",
                        "parts": [{"text": message}]
                    }],
                    turn_complete=True
                )

                # Collect audio response using Live API 2025 format
                audio_chunks = []
                transcript = ""

                async for response in session.receive():
                    logger.debug(f"Live API response: {type(response)}")

                    # Direct audio data access (Live API native format)
                    if hasattr(response, 'data') and response.data is not None:
                        audio_chunks.append(response.data)
                        logger.info(f"Audio chunk received: {len(response.data)} bytes")

                    # Text/transcript response
                    if hasattr(response, 'text') and response.text:
                        transcript += response.text
                        logger.info(f"Transcript: {response.text}")

                    # Check for setup completion and turn completion
                    if hasattr(response, 'setupComplete'):
                        logger.info("Setup complete")
                        continue

                    # Legacy format fallback
                    if hasattr(response, 'server_content') and response.server_content:
                        if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                            logger.info("Turn complete")
                            break

                # Combine all audio chunks
                audio_data = b''.join(audio_chunks) if audio_chunks else None

                return {
                    'audio_data': audio_data,
                    'transcript': transcript,
                    'has_audio': audio_data is not None
                }

        try:
            result = await self.error_handler.handle_with_retry(
                _process,
                self.config.max_retries,
                self.config.retry_delay
            )

            response_time = time.time() - start_time

            return {
                'audio': result.get('audio_data'),
                'transcript': result.get('transcript', ''),
                'response_time': response_time,
                'model': f"{self.config.model} (audio)",
                'type': 'audio_tts',
                'voice': voice_name,
                'success': result.get('has_audio', False),
                'session_id': session_id
            }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Audio processing failed: {e}")

            return {
                'audio': None,
                'transcript': f"Audio processing error: {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': 'error',
                'success': False,
                'session_id': session_id
            }

    async def process_text_with_audio_streaming(
        self,
        message: str,
        voice_name: str = "Aoede",
        session_id: Optional[str] = None,
        callback=None
    ) -> Dict[str, Any]:
        """Process text and return streaming audio response with real-time callback"""

        session_id = session_id or f"audio_stream_{int(time.time())}"
        start_time = time.time()

        # Use WebSocket direct connection for Live API (based on Context7 cookbook)
        from websockets.asyncio.client import connect
        import base64
        import json

        async def _process():
            await self.rate_limiter.wait_if_needed()

            HOST = 'generativelanguage.googleapis.com'
            MODEL = 'models/gemini-2.0-flash-exp'

            ws_url = f'wss://{HOST}/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={self.config.api_key}'

            async with connect(ws_url) as websocket:
                # Send initial setup request
                initial_request = {
                    'setup': {
                        'model': MODEL,
                    },
                }
                await websocket.send(json.dumps(initial_request))

                # Send text input
                text_input = {
                    'clientContent': {
                        'turns': [{
                            'role': 'USER',
                            'parts': [{'text': message}],
                        }],
                        'turnComplete': True,
                    },
                }
                await websocket.send(json.dumps(text_input))

                # Collect and stream response
                audio_chunks = []
                transcript = ""
                chunk_count = 0

                # Process WebSocket messages (based on Context7 cookbook pattern)
                async for msg in websocket:
                    msg_data = json.loads(msg)

                    # Extract audio from server response
                    server_content = msg_data.get('serverContent', {})
                    model_turn = server_content.get('modelTurn', {})

                    current_audio = None
                    current_text = ""

                    for part in model_turn.get('parts', []):
                        # Extract text
                        if 'text' in part:
                            current_text += part['text']
                            transcript += part['text']

                        # Extract audio (base64 encoded)
                        inline_data = part.get('inlineData', {})
                        audio_b64 = inline_data.get('data', '')
                        if audio_b64:
                            current_audio = base64.b64decode(audio_b64)
                            audio_chunks.append(current_audio)

                    # Send streaming update via callback
                    if (current_audio or current_text) and callback:
                        chunk_count += 1
                        await callback({
                            'audio_chunk': current_audio,
                            'text_chunk': current_text,
                            'chunk_id': chunk_count,
                            'session_id': session_id,
                            'is_final': False,
                            'voice': voice_name
                        })

                    # Check for turn completion
                    if server_content.get('turnComplete'):
                        # Send final callback
                        if callback:
                            await callback({
                                'audio_chunk': None,
                                'text_chunk': '',
                                'chunk_id': chunk_count + 1,
                                'session_id': session_id,
                                'is_final': True,
                                'voice': voice_name
                            })
                        break

                    # Handle interruption
                    if 'interrupted' in server_content:
                        logger.info("Stream interrupted by user")
                        break

                # Combine all audio chunks
                audio_data = b''.join(audio_chunks) if audio_chunks else None

                return {
                    'audio_data': audio_data,
                    'transcript': transcript,
                    'has_audio': audio_data is not None,
                    'chunk_count': chunk_count
                }

        try:
            result = await self.error_handler.handle_with_retry(
                _process,
                self.config.max_retries,
                self.config.retry_delay
            )

            response_time = time.time() - start_time

            return {
                'audio': result.get('audio_data'),
                'transcript': result.get('transcript', ''),
                'response_time': response_time,
                'model': f"{self.config.model} (audio_stream)",
                'type': 'audio_streaming',
                'voice': voice_name,
                'success': result.get('has_audio', False),
                'session_id': session_id,
                'chunks_sent': result.get('chunk_count', 0)
            }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Audio streaming processing failed: {e}")

            return {
                'audio': None,
                'transcript': f"Audio streaming error: {str(e)}",
                'response_time': response_time,
                'model': 'error',
                'type': 'error',
                'success': False,
                'session_id': session_id
            }

    async def process_audio_with_audio(
        self,
        audio_bytes: bytes,
        voice_name: str = "Aoede",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process audio input and return audio response (Live API Audio-to-Audio)"""

        session_id = session_id or f"audio_input_{int(time.time())}"
        start_time = time.time()

        async def _process():
            await self.rate_limiter.wait_if_needed()

            # Get voice config from centralized configuration
            gemini_config = AgentConfig.get_gemini_config()
            voice_config = AgentConfig.get_voice_config(voice_name)

            # Create bidirectional audio config (AUDIO input and output)
            audio_config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                temperature=gemini_config.temperature,
                system_instruction="You are a helpful AI assistant. Listen to the user's voice message and respond naturally.",
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_config.name
                        )
                    )
                )
            )

            # Create a new session with audio config
            client = await self.connection_pool.get_client()

            async with client.aio.live.connect(
                model=self.config.model,
                config=audio_config
            ) as session:
                # Send audio data as input with correct format
                await session.send_client_content(
                    turns=[{
                        "role": "user",
                        "parts": [{
                            "inline_data": {
                                "mime_type": "audio/pcm",  # Use PCM for Live API
                                "data": audio_bytes
                            }
                        }]
                    }],
                    turn_complete=True
                )

                # Collect response
                audio_data = None
                transcript = ""
                input_transcript = ""

                async for response in session.receive():
                    # Check for audio data
                    if hasattr(response, 'server_content') and response.server_content:
                        # Input transcription (what user said)
                        if hasattr(response.server_content, 'input_transcription'):
                            if response.server_content.input_transcription:
                                input_transcript = response.server_content.input_transcription.text

                        # Output audio data
                        if hasattr(response.server_content, 'model_turn') and response.server_content.model_turn:
                            model_turn = response.server_content.model_turn
                            if hasattr(model_turn, 'parts') and model_turn.parts:
                                for part in model_turn.parts:
                                    if hasattr(part, 'inline_data') and part.inline_data:
                                        if part.inline_data.mime_type == "audio/pcm":
                                            audio_data = part.inline_data.data

                        # Output transcript (what AI said)
                        if hasattr(response.server_content, 'output_transcription'):
                            if response.server_content.output_transcription:
                                transcript = response.server_content.output_transcription.text

                        if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                            break

                return {
                    'audio_data': audio_data,
                    'transcript': transcript,
                    'input_transcript': input_transcript,
                    'has_audio': audio_data is not None
                }

        try:
            result = await self.error_handler.handle_with_retry(
                _process,
                self.config.max_retries,
                self.config.retry_delay
            )

            response_time = time.time() - start_time

            return {
                'audio': result.get('audio_data'),
                'transcript': result.get('transcript', ''),
                'input_transcript': result.get('input_transcript', ''),
                'response_time': response_time,
                'model': f"{self.config.model} (live_audio)",
                'type': 'audio_live_api',
                'voice': voice_name,
                'success': result.get('has_audio', False),
                'session_id': session_id
            }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Live audio processing failed: {e}")

            return {
                'audio': None,
                'transcript': f"Live audio processing error: {str(e)}",
                'input_transcript': '',
                'response_time': response_time,
                'model': 'error',
                'type': 'error',
                'success': False,
                'session_id': session_id
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