"""
Domain Context

라우팅 컨텍스트 정의 (θ in Integration.md)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class Context:
    """
    라우팅 컨텍스트 (θ)

    차량 정보, 시간, 중량 등을 담는 불변 객체.
    Integration.md의 w'(e;θ) 수식에서 θ에 해당.

    Attributes:
        vehicle_type: 차량 종류 ("truck", "car", "bus")
        current_time: 현재 시각 (시간대 통행 금지 판단용)
        axle_weight: 축 중량 (톤 단위, 중량 제한 판단용)
        permits: 보유 허가증 목록 (조건부 통행 가능 지역용)

    Example:
        >>> from datetime import datetime
        >>> ctx = Context(
        ...     vehicle_type="truck",
        ...     current_time=datetime.now(),
        ...     axle_weight=12.5,
        ...     permits=["hazmat", "oversize"]
        ... )
        >>> ctx.vehicle_type
        'truck'
    """

    vehicle_type: str
    current_time: datetime
    axle_weight: float = 0.0
    permits: List[str] = field(default_factory=list)

    def __post_init__(self):
        """
        유효성 검증

        Raises:
            ValueError: axle_weight가 음수인 경우
            ValueError: vehicle_type이 허용되지 않은 값인 경우
        """
        if self.axle_weight < 0:
            raise ValueError(f"axle_weight must be >= 0, got {self.axle_weight}")

        allowed_types = {"truck", "car", "bus"}
        if self.vehicle_type not in allowed_types:
            raise ValueError(
                f"vehicle_type must be one of {allowed_types}, got '{self.vehicle_type}'"
            )

    def has_permit(self, permit_type: str) -> bool:
        """특정 허가증 보유 여부 확인"""
        return permit_type in self.permits

    def is_truck(self) -> bool:
        """트럭 여부"""
        return self.vehicle_type == "truck"

    def is_bus(self) -> bool:
        """버스 여부"""
        return self.vehicle_type == "bus"

    def is_car(self) -> bool:
        """승용차 여부"""
        return self.vehicle_type == "car"
