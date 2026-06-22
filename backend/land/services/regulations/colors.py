"""
규제별 고유 색상 — 프런트엔드 + CLI 공통 레퍼런스.

Frontend `SiteMapPanel.tsx` 의 `colors` 객체와 동일. 어느 한쪽 변경 시 반드시
양쪽 맞춰야 함 (단일 진실 소스).
"""

COLORS: dict[str, str] = {
    # 핵심 규제 (건축법 본법)
    "buildable_area":                "#22c55e",   # 초록 — 건축가능영역
    "north_setback":                 "#dc2626",   # 진홍 — 정북 일조사선 (2D 선)
    "sunlight_envelope_wall":        "#dc2626",   # 진홍 — 정북 수직 직각벽 (3D Wall)
    "sunlight_envelope_plateau":     "#f472b6",   # 분홍 — 정북 평탄 지붕 (3D 수평 Polygon)
    "sunlight_envelope_slope":       "#ec4899",   # 핑크 — 정북 경사 지붕 (3D 경사 Polygon)
    "adjacent_setback":              "#3b82f6",   # 파랑 — 인접대지 이격선
    "road_setback":                  "#f97316",   # 주황 — 건축선 후퇴
    "corner_cutoff":                 "#eab308",   # 노랑 — 가각전제
    "daylight_diagonal_envelope":    "#a855f7",   # 보라 — 채광사선 경사면 (3D)

    # 지구단위계획 건축선 4종
    "building_designation_line":     "#14b8a6",   # 청록 — 건축지정선
    "building_limit_line":           "#06b6d4",   # 시안 — 건축한계선
    "wall_designation_line":         "#84cc16",   # 라임 — 벽면지정선
    "wall_limit_line":               "#f43f5e",   # 산호 — 벽면한계선
}


COLOR_NAMES_KO: dict[str, str] = {
    "#22c55e": "초록",
    "#dc2626": "진홍",
    "#f472b6": "분홍",
    "#ec4899": "핑크",
    "#3b82f6": "파랑",
    "#f97316": "주황",
    "#eab308": "노랑",
    "#a855f7": "보라",
    "#14b8a6": "청록",
    "#06b6d4": "시안",
    "#84cc16": "라임",
    "#f43f5e": "산호",
}


def get(key: str) -> str:
    """규제 키에 해당하는 hex 색상 반환. 미정의면 회색 fallback."""
    return COLORS.get(key, "#64748b")


def name_ko(hex_color: str) -> str:
    return COLOR_NAMES_KO.get(hex_color, "회색")
