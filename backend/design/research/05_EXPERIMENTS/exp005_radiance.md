# exp005 — A2 Radiance UDI/sDA 실측 — **BLOCKED**

**Date**: 2026-05-06 placeholder, 실측 TBD
**Phase**: 1
**작업 ID**: A2 Radiance lite
**상태**: ⏸️ **BLOCKED** — pyradiance / honeybee-radiance + Radiance 바이너리 미설치

## 차단 사유

본 실험은 외부 의존(Radiance 바이너리 + Python wrapper)에 의존. Windows 환경에서 설치 까다롭고 *별도 PR로 활성화* 가 깔끔.

A2 RadianceEvaluator (`design/services/radiance_evaluator.py`) 인터페이스 + fallback 은 *이미 구현 + 테스트* 완료 (4개 단위 테스트 통과). pyradiance 미설치 시 자동 fallback (기존 daylight_score proxy).

## 활성화 절차 (별도 PR)

1. **Radiance 바이너리 설치**
   - Windows: 별도 인스톨러 (https://www.radiance-online.org/download-install)
   - Or WSL2 + Linux 빌드 (권장)
2. **Python wrapper 설치**
   ```bash
   pip install pyradiance  # or honeybee-radiance
   ```
3. **`radiance_evaluator.py:RADIANCE_AVAILABLE = True` 자동 감지** (이미 코드에 try/import)
4. **`_radiance_compute_udi_sda()` 실제 구현 채움** — footprint→OBJ→scene→rtrace
5. **Seoul.epw 다운로드** → `design/data/weather/Seoul.epw`
6. **본 .md 의 `## 실측 결과` 섹션 채움**

## 가설 (활성화 후 검증)

매스 평가 시간 ~30s/매스. exp001 baseline (1.05s/rep) 대비 **30배 느려짐** → SSIEA 9000 평가 = 75 hours.
→ Phase 2 surrogate (B1) *즉시 트리거*.

## 측정 계획 (활성화 후)

| 매스 | UDI (현재 fallback) | UDI (Radiance) | sDA (Radiance) |
|------|------|------|------|
| 강남 우승 매스 | TBD | TBD | TBD |
| 분당 우승 매스 | TBD | TBD | TBD |
| 춘천 우승 매스 | TBD | TBD | TBD |

## 참조

- `design/services/radiance_evaluator.py` — 인터페이스 + fallback (구현 완료)
- `01_PHASE1/A2_radiance_lite.md` — 작업 설명
- Reinhart, C. F. (2014). UDI methodology
