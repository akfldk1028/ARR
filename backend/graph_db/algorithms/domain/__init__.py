"""
Domain Layer

비즈니스 도메인 모델 (의존성 없음)

Integration.md의 컨텍스트 θ와 규정 타입 정의
"""

from .context import Context
from .types import RegulationType

__all__ = ["Context", "RegulationType"]
