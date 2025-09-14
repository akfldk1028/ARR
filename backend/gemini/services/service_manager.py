"""
Service Manager for Gemini Integration
Handles service lifecycle, configuration, and resource management
"""

import os
import logging
from typing import Optional, Dict, Any
from django.conf import settings

from .gemini_client import OptimizedGeminiClient, ClientConfig


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
        """Load configuration from Django settings and environment"""

        # Get API key from environment or Django settings
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            try:
                api_key = getattr(settings, 'GOOGLE_API_KEY', None)
            except:
                pass

        if not api_key or api_key == "...":
            raise ValueError("GOOGLE_API_KEY not found in environment or Django settings")

        # Load configuration with defaults
        config = ClientConfig(
            api_key=api_key,
            model=os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash-exp"),
            max_connections=int(os.getenv("GEMINI_MAX_CONNECTIONS", "5")),
            connection_timeout=int(os.getenv("GEMINI_CONNECTION_TIMEOUT", "30")),
            request_timeout=int(os.getenv("GEMINI_REQUEST_TIMEOUT", "120")),
            max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("GEMINI_RETRY_DELAY", "1.0")),
            rate_limit_per_minute=int(os.getenv("GEMINI_RATE_LIMIT", "60")),
            enable_compression=os.getenv("GEMINI_COMPRESSION", "true").lower() == "true",
            session_ttl=int(os.getenv("GEMINI_SESSION_TTL", "900"))
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

    async def process_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg"
    ) -> Dict[str, Any]:
        """Process image"""
        return await self.client.process_image(image_bytes, prompt, mime_type)

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