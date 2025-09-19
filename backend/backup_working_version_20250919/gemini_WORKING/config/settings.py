"""
Centralized configuration management for Gemini integration
Environment-aware settings with validation
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class Environment(Enum):
    """Application environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class GeminiConfig:
    """Gemini API configuration"""
    api_key: str
    model: str = "models/gemini-2.0-flash-exp"
    max_connections: int = 5
    connection_timeout: int = 30
    request_timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_per_minute: int = 60
    enable_compression: bool = True
    session_ttl: int = 900  # 15 minutes

    def __post_init__(self):
        if not self.api_key or self.api_key == "...":
            raise ValueError("Invalid or missing GOOGLE_API_KEY")


@dataclass
class WebSocketConfig:
    """WebSocket configuration"""
    max_messages_per_minute: int = 100
    connection_timeout: int = 300  # 5 minutes
    heartbeat_interval: int = 30
    max_message_size: int = 1024 * 1024  # 1MB
    enable_compression: bool = True


@dataclass
class SecurityConfig:
    """Security configuration"""
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 1000
    enable_ddos_protection: bool = True
    allowed_origins: list = field(default_factory=lambda: ["*"])
    require_authentication: bool = False
    max_file_size_mb: int = 10


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: LogLevel = LogLevel.INFO
    enable_file_logging: bool = True
    enable_performance_logging: bool = True
    log_retention_days: int = 30
    enable_structured_logging: bool = False


@dataclass
class CacheConfig:
    """Caching configuration"""
    enabled: bool = True
    default_timeout: int = 300  # 5 minutes
    max_entries: int = 1000
    backend: str = "django.core.cache.backends.locmem.LocMemCache"


@dataclass
class AppConfig:
    """Main application configuration"""
    environment: Environment
    debug: bool
    gemini: GeminiConfig
    websocket: WebSocketConfig
    security: SecurityConfig
    logging: LoggingConfig
    cache: CacheConfig

    @classmethod
    def from_environment(cls) -> 'AppConfig':
        """Create configuration from environment variables"""

        # Determine environment
        env_name = os.getenv('ENVIRONMENT', 'development').lower()
        try:
            environment = Environment(env_name)
        except ValueError:
            environment = Environment.DEVELOPMENT

        # Debug mode
        debug = os.getenv('DEBUG', 'False').lower() == 'true'

        # Gemini configuration
        gemini_config = GeminiConfig(
            api_key=os.getenv('GOOGLE_API_KEY', ''),
            model=os.getenv('GEMINI_MODEL', 'models/gemini-2.0-flash-exp'),
            max_connections=int(os.getenv('GEMINI_MAX_CONNECTIONS', '5')),
            connection_timeout=int(os.getenv('GEMINI_CONNECTION_TIMEOUT', '30')),
            request_timeout=int(os.getenv('GEMINI_REQUEST_TIMEOUT', '120')),
            max_retries=int(os.getenv('GEMINI_MAX_RETRIES', '3')),
            retry_delay=float(os.getenv('GEMINI_RETRY_DELAY', '1.0')),
            rate_limit_per_minute=int(os.getenv('GEMINI_RATE_LIMIT', '60')),
            enable_compression=os.getenv('GEMINI_COMPRESSION', 'true').lower() == 'true',
            session_ttl=int(os.getenv('GEMINI_SESSION_TTL', '900'))
        )

        # WebSocket configuration
        websocket_config = WebSocketConfig(
            max_messages_per_minute=int(os.getenv('WS_MAX_MESSAGES_PER_MINUTE', '100')),
            connection_timeout=int(os.getenv('WS_CONNECTION_TIMEOUT', '300')),
            heartbeat_interval=int(os.getenv('WS_HEARTBEAT_INTERVAL', '30')),
            max_message_size=int(os.getenv('WS_MAX_MESSAGE_SIZE', str(1024 * 1024))),
            enable_compression=os.getenv('WS_COMPRESSION', 'true').lower() == 'true'
        )

        # Security configuration
        security_config = SecurityConfig(
            enable_rate_limiting=os.getenv('SECURITY_RATE_LIMITING', 'true').lower() == 'true',
            max_requests_per_minute=int(os.getenv('SECURITY_MAX_REQUESTS_PER_MINUTE', '1000')),
            enable_ddos_protection=os.getenv('SECURITY_DDOS_PROTECTION', 'true').lower() == 'true',
            allowed_origins=os.getenv('SECURITY_ALLOWED_ORIGINS', '*').split(','),
            require_authentication=os.getenv('SECURITY_REQUIRE_AUTH', 'false').lower() == 'true',
            max_file_size_mb=int(os.getenv('SECURITY_MAX_FILE_SIZE_MB', '10'))
        )

        # Logging configuration
        log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
        try:
            log_level = LogLevel(log_level_str)
        except ValueError:
            log_level = LogLevel.INFO

        logging_config = LoggingConfig(
            level=log_level,
            enable_file_logging=os.getenv('LOG_FILE_ENABLED', 'true').lower() == 'true',
            enable_performance_logging=os.getenv('LOG_PERFORMANCE_ENABLED', 'true').lower() == 'true',
            log_retention_days=int(os.getenv('LOG_RETENTION_DAYS', '30')),
            enable_structured_logging=os.getenv('LOG_STRUCTURED', 'false').lower() == 'true'
        )

        # Cache configuration
        cache_config = CacheConfig(
            enabled=os.getenv('CACHE_ENABLED', 'true').lower() == 'true',
            default_timeout=int(os.getenv('CACHE_DEFAULT_TIMEOUT', '300')),
            max_entries=int(os.getenv('CACHE_MAX_ENTRIES', '1000')),
            backend=os.getenv('CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache')
        )

        return cls(
            environment=environment,
            debug=debug,
            gemini=gemini_config,
            websocket=websocket_config,
            security=security_config,
            logging=logging_config,
            cache=cache_config
        )

    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT

    def get_client_config(self):
        """Get Gemini client configuration"""
        from ..services.gemini_client import ClientConfig
        return ClientConfig(
            api_key=self.gemini.api_key,
            model=self.gemini.model,
            max_connections=self.gemini.max_connections,
            connection_timeout=self.gemini.connection_timeout,
            request_timeout=self.gemini.request_timeout,
            max_retries=self.gemini.max_retries,
            retry_delay=self.gemini.retry_delay,
            rate_limit_per_minute=self.gemini.rate_limit_per_minute,
            enable_compression=self.gemini.enable_compression,
            session_ttl=self.gemini.session_ttl
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'environment': self.environment.value,
            'debug': self.debug,
            'gemini': {
                'model': self.gemini.model,
                'max_connections': self.gemini.max_connections,
                'rate_limit_per_minute': self.gemini.rate_limit_per_minute,
            },
            'websocket': {
                'max_messages_per_minute': self.websocket.max_messages_per_minute,
                'connection_timeout': self.websocket.connection_timeout,
            },
            'security': {
                'enable_rate_limiting': self.security.enable_rate_limiting,
                'max_file_size_mb': self.security.max_file_size_mb,
            }
        }


# Global configuration instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        _config = AppConfig.from_environment()
    return _config


def reload_config() -> AppConfig:
    """Reload configuration from environment"""
    global _config
    _config = AppConfig.from_environment()
    return _config