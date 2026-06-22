# C3 — Differentiable Rendering

**기간**: 4-8주 | **학습**: ❌ (Mitsuba 3 사용) | GPU 권장

## 목적
GA의 *시행착오 탐색* → gradient descent로 직접 이동. *어느 방향으로 매스 변형하면 일조 좋아지는지* 미분으로 직접 안다.

## 도구
- **Mitsuba 3** (EPFL) — 미분 가능 렌더러
- **Pytorch3D** — 3D mesh + rendering, PyTorch 통합

## 흐름
1. 매스 (mesh 또는 SDF) → Mitsuba 3 scene
2. 일조 점수 → 매스 vertex/parameter에 대한 ∂L/∂x 계산
3. Adam optimizer로 gradient descent

## 검증
- GA + Radiance vs Gradient + Mitsuba 3 — 수렴 속도 비교 (예상 100배 차이)
- 동일 부지 결과 일관성

## 학계 참고
- SDF Differentiable Rendering SIGGRAPH Asia 2024 (Vicini)
- ICCV 2025 — Higher-order Differentiable Rendering (Wang)

## 의존성
- PyTorch, CUDA, Mitsuba 3 — `requirements.txt` 추가
