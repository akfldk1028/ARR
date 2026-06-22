# ARR/backend/tools — 규제선 + 법규 CLI 검증 도구

**목적**: /design 페이지를 브라우저로 열지 않고 CLI에서 필지 규제선 8종 + BCR/FAR 수치 정확성을 즉시 검증.

이 폴더는 **다음 세션 AI가 바로 쓸 수 있도록 자기완결적**으로 설계됨. `test_parcels.json` 픽스처 + 단건/배치 CLI 두 개.

## 빠른 시작

```bash
# 전제: Django :8000, law-domain-agents :8011, Neo4j :7687 모두 기동

cd ARR/backend

# 단건 검증 (PNU 하나)
PYTHONIOENCODING=utf-8 python tools/verify_setbacks.py 1168010100106770000

# 배치 검증 (test_parcels.json 전체, 9개 필지, 5개 용도지역)
PYTHONIOENCODING=utf-8 python tools/verify_all.py

# 주거지역만 필터
PYTHONIOENCODING=utf-8 python tools/verify_all.py --filter 주거
```

Windows cp949 콘솔 인코딩 때문에 `PYTHONIOENCODING=utf-8` **반드시** 필요.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `verify_setbacks.py` | 단건 CLI — 지정된 PNU 하나의 BCR/FAR 법 상한 비교 + 규제선 8종 상태 상세 출력 |
| `verify_all.py` | 배치 — `test_parcels.json` 전체를 돌면서 용도지역별 pass/fail 집계 |
| `test_parcels.json` | 9개 대표 PNU 픽스처 (중심상업/일반상업/제1종전용주거/제2종일반주거/제3종일반주거), 각 PNU에 기대값(BCR/FAR/sunlight_applies) + 기대 규제선 목록 포함 |

## 검증 대상 규제선 8종

| 키 | 적용 대상 | 법근거 |
|---|---|---|
| `buildable_area` | 모든 용도지역 | 이격거리 전체 적용 후 건축가능 폴리곤 |
| `north_setback` | 전용주거+일반주거만 | 건축법 §61, 시행령 §86 |
| `adjacent_setback` | 전 용도지역 | 건축법 §58 (기본 0.5m) |
| `road_setback` | 전 용도지역 | 건축법 §46-47 |
| `corner_cutoff` | 8m 미만 도로 모퉁이 | 시행령 §31 |
| `building_designation_line` | 지구단위계획구역만 | 지구단위계획 조례 |
| `sunlight_envelope` (3D wall) | 전용주거+일반주거 | 건축법 §61 — H≤10m: 1.5m, H>10m: H×0.5 |
| `daylight_diagonal_envelope` (3D wall) | 공동주택 | 시행령 §86 — 채광방향 인접경계 |

## 종료 코드

- `0` — 전부 pass
- `1` — 입력 오류 / 백엔드 연결 실패
- `2` — 일부 필지 검증 실패 (수치 불일치 or 선 누락)

## 픽스처 갱신

새 PNU 추가하려면:
1. `/land/resolve/` POST `{"input": "주소", "input_type":"address"}` → PNU 받기
2. `/design/site-boundary/` + `/design/auto-constraints/` 한 번 호출해서 zone/BCR/FAR 확인
3. `test_parcels.json`의 `parcels` 배열에 아래 형식으로 추가:

```json
{
  "pnu": "...",
  "address": "...",
  "zone": "제3종일반주거지역",
  "expected": {"bcr_pct": 50, "far_pct": 300, "sunlight_applies": true},
  "expected_lines_drawn": ["buildable_area", "north_setback", "adjacent_setback", ...],
  "expected_na": ["building_designation_line"],
  "area_m2": 437.85,
  "notes": "..."
}
```

## 관련 코드 포인터

- 백엔드 규제선 계산: `ARR/backend/land/services/setback_geometry.py`
- BCR/FAR 매칭: `ARR/backend/land/services/zoning_mapper.py` + `land/data/zoning_limits.json`
- API 엔드포인트: `ARR/backend/design/views.py` → `auto_constraints()`
- 프런트 렌더: `ARR/frontend/src/design/components/SiteMapPanel.tsx` → `renderSetbackEntities()`

## 알려진 이슈

- `사직동 1 (1111011500100010001)`: BCR=20%, FAR=100% 반환 — 제2종일반주거 기대값(60/200)과 불일치. 경복궁 인접 문화재구역 overlay 영향 가능성. 픽스처의 `notes` 참조.
- 일부 주소는 `/land/resolve/` 에서 geocoding 실패 가능 (Vworld가 도로명주소만 받기도 함). 지번주소로 재시도 권장.
- `LLM_EXTRACTION_ENABLED=true` 기본값이면 `adjacent_setback_m` 가 LLM 추출값(6m 등)으로 override될 수 있음. 순수 static 검증시 `LLM_EXTRACTION_ENABLED=false` 환경변수 지정.
