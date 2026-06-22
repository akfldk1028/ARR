# A7 — Constraint Visualizer (envelope + 매스 동시 표시)

**기간**: 3-5일 | **학습**: ❌ | **ROI 4.0**

## 목적
플렉시티 광고처럼 envelope(녹색) + 매스(노란색) + 사선 라벨(정북일조/도로/이격) 동시 표시. 사용자에게 *왜 이런 매스가 되었는지* 시각적 설명.

## 작업

### Frontend
- `ARR/frontend/src/design/SiteMapPanel.tsx` 수정
- Cesium에 다음 layer 추가:
  1. **노란색 매스** (현재 있음)
  2. **녹색 반투명 envelope** (정북일조 + 도로사선 합쳐진 면)
  3. **빨간 점선** (대지 안의 공지 = 이격선)
  4. **라벨** ("정북 일조 사선", "9m 도로 후퇴", "대지 안의 공지", "코어 계획")

### Backend
- `ARR/backend/design/services/mass_renderer.py` 에 envelope GeoJSON 출력 추가
- `mass_renderer.py:render()` → `{ mass: GeoJSON, envelope: GeoJSON, setback: GeoJSON, labels: [...] }`

### envelope 데이터 출처
- 이미 `envelopes/sunlight.py` LOCKED — 정북일조 사선 면 좌표 있음
- 도로 사선/이격선 — `regulation_validator.py` 또는 신규 함수에서 계산

## 검증
- 강남구 역삼동 677 부지로 테스트
- 매스가 envelope 안에 *시각적으로* fit 되는지
- 라벨이 정확한 위치에 표시되는지

## 발표 효과
교수님 시연 시 *"여기가 정북일조 사선이고, 매스가 그 안에 들어갔습니다"* 직접 보여줄 수 있음. 플렉시티 광고와 *같은 시각적 임팩트*.

## 의존성
- 기존 Cesium 3D Viewer (이미 있음)
- envelope GeoJSON 변환 함수 (신규)
