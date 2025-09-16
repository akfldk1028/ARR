"""
API Configuration
External API 관련 설정을 관리합니다.
"""

import os
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class APIEndpoint:
    """API 엔드포인트 설정"""
    base_url: str
    timeout: int = 30
    max_retries: int = 3
    rate_limit: int = 60  # requests per minute


class APIConfig:
    """API 관련 설정 관리"""

    # API Keys
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

    # External APIs
    ENDPOINTS = {
        'google_ai': APIEndpoint(
            base_url='https://generativelanguage.googleapis.com',
            timeout=int(os.getenv('GOOGLE_TIMEOUT', '120')),
            max_retries=int(os.getenv('GOOGLE_MAX_RETRIES', '3')),
            rate_limit=int(os.getenv('GOOGLE_RATE_LIMIT', '60'))
        ),
    }

    @classmethod
    def get_api_key(cls, service: str) -> Optional[str]:
        """API 키 반환"""
        key_map = {
            'google': cls.GOOGLE_API_KEY,
            'openai': cls.OPENAI_API_KEY,
            'anthropic': cls.ANTHROPIC_API_KEY,
        }
        return key_map.get(service)

    @classmethod
    def get_endpoint(cls, service: str) -> Optional[APIEndpoint]:
        """API 엔드포인트 설정 반환"""
        return cls.ENDPOINTS.get(service)

    @classmethod
    def validate_keys(cls) -> Dict[str, bool]:
        """모든 API 키 검증"""
        return {
            'google': bool(cls.GOOGLE_API_KEY and cls.GOOGLE_API_KEY != '...'),
            'openai': bool(cls.OPENAI_API_KEY and cls.OPENAI_API_KEY != '...'),
            'anthropic': bool(cls.ANTHROPIC_API_KEY and cls.ANTHROPIC_API_KEY != '...'),
        }