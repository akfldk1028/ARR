"""
Service Manager for Gemini Integration
Handles service lifecycle, configuration, and resource management
"""

import os
import logging
from typing import Optional, Dict, Any
from django.conf import settings

from .gemini_client import OptimizedGeminiClient, ClientConfig
# Import centralized configuration
from config.agent_config import AgentConfig
from config.api_config import APIConfig
from config.app_settings import AppSettings


logger = logging.getLogger(__name__)


class ServiceManager:
    """Singleton service manager for Gemini client"""

    _instance: Optional['ServiceManager'] = None
    _client: Optional[OptimizedGeminiClient] = None

    def __new__(cls) -> 'ServiceManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self._initialize()
            self.initialized = True

    def _initialize(self):
        """Initialize the service manager"""
        try:
            config = self._load_config()
            self._client = OptimizedGeminiClient(config)
            logger.info("Service manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize service manager: {e}")
            raise

    def _load_config(self) -> ClientConfig:
        """Load configuration from centralized config management"""

        # Get API key from centralized configuration
        api_key = APIConfig.get_api_key('google')
        if not api_key or api_key == "...":
            raise ValueError("GOOGLE_API_KEY not found. Please set GOOGLE_API_KEY environment variable.")

        # Get Gemini configuration from centralized config
        gemini_config = AgentConfig.get_gemini_config()
        app_config = AppSettings.get_config()

        # Build client configuration using centralized settings
        config = ClientConfig(
            api_key=api_key,
            model=gemini_config.model,
            max_connections=5,  # Could be moved to config later
            connection_timeout=gemini_config.connection_timeout,
            request_timeout=gemini_config.request_timeout,
            max_retries=gemini_config.max_retries,
            retry_delay=gemini_config.retry_delay,
            rate_limit_per_minute=app_config['rate_limit']['requests_per_minute'],
            enable_compression=True,  # Could be moved to config later
            session_ttl=app_config['session']['ttl']
        )

        logger.info(f"Loaded config for model: {config.model}")
        return config

    @property
    def client(self) -> OptimizedGeminiClient:
        """Get the Gemini client instance"""
        if not self._client:
            raise RuntimeError("Service manager not properly initialized")
        return self._client

    async def process_text(
        self,
        message: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process text message"""
        return await self.client.process_text_stream(message, session_id)

    async def process_text_with_streaming(
        self,
        message: str,
        session_id: Optional[str] = None,
        callback=None
    ) -> Dict[str, Any]:
        """Process text message with real-time streaming callback"""
        return await self.client.process_text_stream_with_callback(message, session_id, callback)

    async def process_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg"
    ) -> Dict[str, Any]:
        """Process image"""
        return await self.client.process_image(image_bytes, prompt, mime_type)

    async def process_text_with_audio(
        self,
        message: str,
        voice_name: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process text with audio response (TTS)"""
        # Use default voice from config if none specified
        if voice_name is None:
            gemini_config = AgentConfig.get_gemini_config()
            voice_name = gemini_config.default_voice

        return await self.client.process_text_with_audio(message, voice_name, session_id)

    async def process_text_with_audio_streaming(
        self,
        message: str,
        voice_name: Optional[str] = None,
        session_id: Optional[str] = None,
        callback=None
    ) -> Dict[str, Any]:
        """Process text with streaming audio response (TTS)"""
        # Use default voice from config if none specified
        if voice_name is None:
            gemini_config = AgentConfig.get_gemini_config()
            voice_name = gemini_config.default_voice

        return await self.client.process_text_with_audio_streaming(message, voice_name, session_id, callback)

    async def process_audio_with_audio(
        self,
        audio_bytes: bytes,
        voice_name: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process audio input with audio response (Live API Audio-to-Audio)"""
        # Use default voice from config if none specified
        if voice_name is None:
            gemini_config = AgentConfig.get_gemini_config()
            voice_name = gemini_config.default_voice

        return await self.client.process_audio_with_audio(audio_bytes, voice_name, session_id)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        return await self.client.health_check()

    async def cleanup(self):
        """Cleanup resources"""
        if self._client:
            await self._client.cleanup()
        logger.info("Service manager cleanup completed")

    @classmethod
    def get_instance(cls) -> 'ServiceManager':
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Global service instance
def get_gemini_service() -> ServiceManager:
    """Get the global Gemini service instance"""
    return ServiceManager.get_instance()