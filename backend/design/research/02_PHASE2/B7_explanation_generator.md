# B7 — Explanation Generator ✅ DONE — template + LLM dual mode (2026-05-06 21:36)

## 상태: COMPLETE

**기간**: 1-2주 예상 → 1시간 (template + LLM dual implementation)
**학습**: ❌ (LLM API 호출만, 또는 offline template)
**구현**: `design/services/explanation_generator.py`
**실험**: `05_EXPERIMENTS/exp013_*.md`

## 원리

**Dual mode**:
1. **LLM 모드** (gpt-4o-mini, OPENAI_API_KEY 필요): 자연스러운 한국어 paragraph
2. **Template fallback** (offline): 정해진 구조 + 동적 수치 삽입

**입력**:
- mass_evaluator outputs (BCR/FAR/daylight/height/setback)
- typology (B5 추천)
- site (zone/limits)
- precedent (B3 RAG, optional)
- core (B6 plan, optional)

**Template 구조**:
1. 도입 — 무엇을 추천 (typology 한국어 + 층수)
2. 규제 검증 — BCR/FAR/높이 + ✅/⚠️ 표시
3. 면적 + 일조 점수
4. (주거지역만) 정북일조 §86① 언급
5. (코어 있으면) 코어 위치 + 마진
6. (사례 있으면) 비슷한 사례 1건 인용

## 출력 예시 (template)

```
본 부지(일반상업지역)에 박스 제거형 매스를 6층 규모로 추천합니다.

규제 검증: 건폐율 56.3% (한도 80%) ✅, 용적률 951.3% (한도 1300%) ✅,
높이 16.8m (한도 50m) ✅, 인접대지 이격 3.05m.

총 연면적 5,142m², 일조 점수 72/100점.

비슷한 사례: 강남 테헤란로 일반상업 — 매스 형태 tower_podium ...
```

## API

```python
from design.services.explanation_generator import generate_explanation
text = generate_explanation(
    metrics={"bcr": 56, "far": 230, ...},
    typology="subtractive",
    site={"zone": "일반상업지역", "bcr_limit": 80, ...},
    precedent={"name": "강남 테헤란로", ...},  # B3 RAG 결과
    core=core_plan,                            # B6 결과
    use_llm=True,  # OPENAI_API_KEY 있으면 LLM, 없으면 template
)
```

## 회귀
**171/171 design 테스트 통과** (4 신규 ExplanationGeneratorTest).

---

## (Original Plan)

## 목적
플렉시티 광고처럼 *"20년차 건축사 사고과정"* 일부 모방. LLM이 매스를 보고 *왜 이렇게 되었는지* 한국어 설명 생성.

## 흐름
1. 매스 결정 후 → JSON으로 (BCR, FAR, 일조 점수, 적용된 사선 등)
2. LLM (GPT-5 또는 Claude Opus 4) 에 prompt:
```
부지 정보: {pnu, 용도지역, 면적, 도로 폭, 인접대지}
법규 제약: {정북일조 4단계 사선, 9m 도로 후퇴, 3m 인접 이격, BCR 60%, FAR 250%}
생성된 매스: {박스 5개 좌표/크기, 층수 5, 면적 X, 일조 점수 0.85}
적용된 사선: 정북일조 (북측 13m 후퇴), 도로 사선 (남측 5m 후퇴)
적용된 코어: 동측 30m² (계단실 + 엘리베이터 2기)

위 결정을 *건축사가 설명하듯이* 4-5문장으로 한국어로 풀어 주세요.
```

## 출력 예시
> *"북측 인접 대지가 13m 떨어져 있어 정북일조 4단계 사선을 적용한 결과, 매스의 북동측 상층부가 단차를 이루며 후퇴했습니다. 도로 사선은 남측 5m 후퇴로 처리했고, BCR 58%, FAR 245%로 법규 한도(60%, 250%) 안에 안전하게 들어갑니다. 코어는 동측 측벽에 배치해 자연광 손실을 최소화했고, 피난 동선은 28m로 30m 이내 만족합니다."*

## 작업
- `ARR/backend/design/services/explanation_generator.py` (신규)
- LLM API 호출 (OpenAI 또는 Anthropic)
- 결과를 SSE stream에 *마지막 이벤트* 로 추가

## 검증
- 강남구 역삼동 677 부지 + 강남구 + 분당 + 춘천 4곳 테스트
- 도메인 전문가 검토 (정확도, 자연스러움)

## 학계 참고
- LLM-FuncMapper (Wu 2023) — building code → function 매핑
- 기존 우리 RAG (`law_enricher.py`) 와 통합 가능
