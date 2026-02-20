"""
Domain Types

비즈니스 도메인 타입 정의 (의존성 없음)
"""

from enum import Enum


class RegulationType(str, Enum):
    """
    규정 타입 (Integration.md 4절 참조)

    차단 규칙 (Blocking):
        - ONEWAY: 일방통행 위반
        - TIME_BAN: 시간대 통행 금지
        - WEIGHT_LIMIT: 중량 제한 위반

    페널티 규칙 (Penalty):
        - BUS_ONLY: 버스 전용 차로
        - TOLL: 유료 도로 통행료
        - SCHOOL_ZONE: 어린이 보호 구역

    조건부 규칙 (Conditional):
        - PERMIT_BASED: 허가증 기반 통제
    """

    # 차단 규칙 (w'(e;θ) = +∞)
    ONEWAY = "oneway"
    TIME_BAN = "timeBan"
    WEIGHT_LIMIT = "weightLimit"

    # 페널티 규칙 (w'(e;θ) = w(e) + penalty)
    BUS_ONLY = "busOnly"
    TOLL = "toll"
    SCHOOL_ZONE = "schoolZone"

    # 조건부 규칙
    PERMIT_BASED = "permitBased"

    def is_blocking(self) -> bool:
        """차단 규칙 여부 (위반 시 통행 불가)"""
        return self in {
            RegulationType.ONEWAY,
            RegulationType.TIME_BAN,
            RegulationType.WEIGHT_LIMIT,
        }

    def is_penalty(self) -> bool:
        """페널티 규칙 여부 (위반 시 비용 증가)"""
        return self in {
            RegulationType.BUS_ONLY,
            RegulationType.TOLL,
            RegulationType.SCHOOL_ZONE,
        }
