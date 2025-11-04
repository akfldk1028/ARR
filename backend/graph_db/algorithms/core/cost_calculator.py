"""
Cost Calculator

엣지 비용 계산기 (Integration.md w'(e;θ) 구현)
"""

from typing import Dict, List
from ..domain import Context, RegulationType


class CostCalculator:
    """
    엣지 비용 계산기

    Integration.md의 w'(e;θ) 공식 구현:
        - w'(e;θ) = w(e) + Σ penalty  (통행 가능한 경우)
        - w'(e;θ) = +∞                 (통행 불가능한 경우)

    순수 함수형 설계 (상태 없음, Neo4j 독립)
    """

    INF = 10**18  # 차단 표시용 무한대 (Integration.md 참조)

    def calculate_edge_cost(
        self, base_cost: float, regulations: List[Dict], context: Context
    ) -> float:
        """
        엣지 비용 계산

        Args:
            base_cost: 기본 비용 w(e) (초 단위 주행 시간)
            regulations: 적용 가능한 규정 목록
                각 규정은 다음 키를 포함:
                    - type: 규정 타입 (RegulationType 값)
                    - limit: 중량 제한 (weightLimit 타입)
                    - start_time, end_time: 시간대 (timeBan 타입)
                    - penalty: 페널티 비용 (toll, busOnly 등)
                    - required_permit: 필요 허가증 (permitBased 타입)
            context: 라우팅 컨텍스트 θ (차량 정보, 시간 등)

        Returns:
            최종 비용 w'(e;θ)
                - 통행 가능: base_cost + 페널티 합산
                - 통행 불가: INF (10^18)

        Example:
            >>> from datetime import datetime
            >>> from ..domain import Context
            >>> calc = CostCalculator()
            >>> ctx = Context("truck", datetime.now(), 12.0, [])
            >>> regs = [{"type": "weightLimit", "limit": 10.0}]
            >>> cost = calc.calculate_edge_cost(100.0, regs, ctx)
            >>> cost == CostCalculator.INF
            True
        """
        total_cost = base_cost

        for reg in regulations:
            reg_type_str = reg.get("type")
            if not reg_type_str:
                continue

            try:
                reg_type = RegulationType(reg_type_str)
            except ValueError:
                # 알 수 없는 규정 타입은 무시
                continue

            # 차단 규칙 검증
            if reg_type.is_blocking():
                if self._is_blocked(reg, reg_type, context):
                    return self.INF

            # 페널티 규칙 적용
            elif reg_type.is_penalty():
                penalty = self._calculate_penalty(reg, reg_type, context)
                total_cost += penalty

        return total_cost

    def _is_blocked(
        self, regulation: Dict, reg_type: RegulationType, context: Context
    ) -> bool:
        """
        차단 규칙 위반 여부 판단

        Returns:
            True: 통행 불가 (비용 = INF)
            False: 통행 가능
        """
        if reg_type == RegulationType.WEIGHT_LIMIT:
            limit = regulation.get("limit", 0.0)
            return context.is_truck() and context.axle_weight > limit

        elif reg_type == RegulationType.TIME_BAN:
            # 시간대 통행 금지 (예: 07:00-09:00 또는 22:00-06:00)
            start_time = regulation.get("start_time")  # datetime.time 객체
            end_time = regulation.get("end_time")
            if start_time and end_time:
                current_time = context.current_time.time()

                # 자정 넘김 처리
                if start_time <= end_time:
                    # 일반 케이스: 09:00 ~ 18:00
                    if start_time <= current_time <= end_time:
                        return True
                else:
                    # 자정 넘김: 22:00 ~ 06:00
                    # (22:00 이후) OR (06:00 이전)
                    if current_time >= start_time or current_time <= end_time:
                        return True

        elif reg_type == RegulationType.ONEWAY:
            # 일방통행 위반 (간단 구현: 항상 차단)
            # 실제로는 엣지 방향과 비교 필요
            return regulation.get("violated", False)

        elif reg_type == RegulationType.PERMIT_BASED:
            # 허가증 필요 지역
            required_permit = regulation.get("required_permit")
            if required_permit and not context.has_permit(required_permit):
                return True

        return False

    def _calculate_penalty(
        self, regulation: Dict, reg_type: RegulationType, context: Context
    ) -> float:
        """
        페널티 비용 계산

        Returns:
            추가 비용 (초 단위 또는 비용 단위)
        """
        penalty = regulation.get("penalty", 0.0)

        if reg_type == RegulationType.BUS_ONLY:
            # 버스 전용 차로: 버스가 아니면 페널티
            if not context.is_bus():
                return penalty
            return 0.0

        elif reg_type == RegulationType.TOLL:
            # 유료 도로: 모든 차량에 통행료
            return penalty

        elif reg_type == RegulationType.SCHOOL_ZONE:
            # 어린이 보호 구역: 제한 속도로 인한 시간 증가
            return penalty

        return 0.0
