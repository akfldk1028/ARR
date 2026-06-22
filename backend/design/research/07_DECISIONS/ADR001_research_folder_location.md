# ADR-001 — research 폴더 위치

**Date**: 2026-05-06
**Status**: ✅ Accepted

## Context
매스 자동화 연구 자료(.md) 어디에 둘 것인가? 후보 4개:
1. `ARR/backend/design/research/` (design 앱 안)
2. `ARR/backend/design_research/` (별도 Django 앱)
3. `AG/agent/mass-design-agent/` (새 agent 시스템)
4. 분산 통합

## Decision
**1번 선택**: `ARR/backend/design/research/`

## Rationale
- 기존 `engine/objects.py`, `services/mass_evaluator.py` 와 *상호 참조 자연스러움*
- 향후 `research/04_DATASETS/` 학습 데이터를 `services/surrogate_loader.py` 등에서 *직접 import 가능*
- 별도 앱 분리는 데이터셋/모델 API가 *충분히 커진 후* (ADR 별도 결정)
- 사용자(2026-05-06) 명시 선택

## Consequences
- 장점: 코드 + 연구 자료 한 폴더, 컨텍스트 공유
- 단점: design 앱 부피 증가. 향후 분리 작업 발생 가능성
