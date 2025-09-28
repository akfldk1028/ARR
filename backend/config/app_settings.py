"""
Application-wide Settings
애플리케이션 전체 설정을 관리합니다.
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AppSettings:
    """애플리케이션 전체 설정"""

    # ===== Environment =====
    ENV = os.getenv('ENV', 'development')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

    # ===== Server =====
    HOST = os.getenv('HOST', 'localhost')
    PORT = int(os.getenv('PORT', '8000'))

    # ===== Database =====
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///db.sqlite3')

    # ===== WebSocket =====
    WEBSOCKET_CONFIG = {
        'max_connections': int(os.getenv('WS_MAX_CONNECTIONS', '100')),
        'timeout': int(os.getenv('WS_TIMEOUT', '60')),
        'ping_interval': int(os.getenv('WS_PING_INTERVAL', '30')),
    }

    # ===== Logging =====
    LOGGING_CONFIG = {
        'level': os.getenv('LOG_LEVEL', 'INFO'),
        'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        'file': os.getenv('LOG_FILE', 'logs/app.log'),
    }

    # ===== Session =====
    SESSION_CONFIG = {
        'ttl': int(os.getenv('SESSION_TTL', '900')),  # 15 minutes
        'max_history': int(os.getenv('SESSION_MAX_HISTORY', '100')),
    }

    # ===== Rate Limiting =====
    RATE_LIMIT_CONFIG = {
        'requests_per_minute': int(os.getenv('RATE_LIMIT_RPM', '60')),
        'requests_per_hour': int(os.getenv('RATE_LIMIT_RPH', '1000')),
    }

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """전체 설정을 딕셔너리로 반환"""
        return {
            'env': cls.ENV,
            'debug': cls.DEBUG,
            'host': cls.HOST,
            'port': cls.PORT,
            'database_url': cls.DATABASE_URL,
            'websocket': cls.WEBSOCKET_CONFIG,
            'logging': cls.LOGGING_CONFIG,
            'session': cls.SESSION_CONFIG,
            'rate_limit': cls.RATE_LIMIT_CONFIG,
        }

    @classmethod
    def is_production(cls) -> bool:
        """운영 환경인지 확인"""
        return cls.ENV == 'production'

    @classmethod
    def is_development(cls) -> bool:
        """개발 환경인지 확인"""
        return cls.ENV == 'development'