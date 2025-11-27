"""
Phase 2.0: 병렬 A2A 협업 테스트
DynTaskMAS APEE 패턴 적용 성능 검증

목표:
1. 순차 실행 대비 병렬 실행 속도 비교
2. "용도지역" 쿼리로 A2A 협업 트리거
3. 응답 시간 측정 (목표: 47초 → 18초, 약 60% 단축)
4. 결과 품질 유지 확인

References:
- DynTaskMAS (ICAPS 2025): arXiv:2503.07675
- Phase 1.9: JO_BOOST_FACTOR = 40 성공
"""

import requests
import json
import time
from pathlib import Path

API_URL = "http://127.0.0.1:8000/agents/law/api/search"

def test_parallel_a2a():
    """병렬 A2A 협업 테스트"""

    print("=" * 80)
    print("Phase 2.0: 병렬 A2A 협업 테스트 (DynTaskMAS APEE 패턴)")
    print("=" * 80)

    # API 요청
    payload = {
        "query": "용도지역",
        "limit": 10
    }

    print(f"\n[Request]")
    print(f"URL: {API_URL}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    try:
        print(f"\n[Executing] API 호출 중...")
        start_time = time.time()

        response = requests.post(API_URL, json=payload, timeout=120)

        elapsed_time = time.time() - start_time

        print(f"\n[Response]")
        print(f"Status Code: {response.status_code}")
        print(f"Total Elapsed Time: {elapsed_time:.2f}s")

        if response.status_code == 200:
            data = response.json()

            # 결과 저장
            output_path = Path(__file__).parent / "a2a_parallel_results.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"Response saved to: {output_path}")

            # 분석
            print("\n" + "=" * 80)
            print("결과 분석")
            print("=" * 80)

            # 1. 응답 시간 비교
            response_time_ms = data.get('response_time', 0)
            response_time_s = response_time_ms / 1000

            print(f"\n[1] 성능 비교")
            print(f"  Total API Time: {elapsed_time:.2f}s")
            print(f"  Backend Response Time: {response_time_s:.2f}s")
            print(f"  Network Overhead: {elapsed_time - response_time_s:.2f}s")

            # Phase 1.9 기준 (순차 실행)
            baseline_time = 46.845  # yongdo_search_results.json
            improvement = ((baseline_time - response_time_s) / baseline_time) * 100

            print(f"\n  📊 성능 개선:")
            print(f"    Phase 1.9 (순차): {baseline_time:.2f}s")
            print(f"    Phase 2.0 (병렬): {response_time_s:.2f}s")
            print(f"    개선율: {improvement:.1f}%")

            if improvement >= 50:
                print(f"    ✅ SUCCESS: {improvement:.1f}% 개선 (목표: 60%)")
            elif improvement >= 30:
                print(f"    ⚠️  PARTIAL: {improvement:.1f}% 개선 (목표 미달)")
            else:
                print(f"    ❌ FAIL: {improvement:.1f}% 개선만 달성")

            # 2. A2A 협업 분석
            print(f"\n[2] A2A 협업 분석")
            stats = data.get('stats', {})

            a2a_triggered = stats.get('a2a_collaboration_triggered', False)
            a2a_count = stats.get('a2a_collaborations', 0)
            a2a_results = stats.get('a2a_results_count', 0)

            domains_queried = data.get('domains_queried', [])
            a2a_domains = data.get('a2a_domains', [])

            print(f"  A2A 협업 발동: {'✅ YES' if a2a_triggered else '❌ NO'}")
            print(f"  협업 도메인 수: {a2a_count}개")
            print(f"  A2A 결과 수: {a2a_results}개")
            print(f"\n  쿼리된 도메인:")
            for domain in domains_queried:
                is_a2a = domain in a2a_domains
                marker = "🔗 (A2A)" if is_a2a else "🏠 (My)"
                print(f"    {marker} {domain}")

            # 3. 결과 품질 분석
            print(f"\n[3] 결과 품질")
            results = data.get('results', [])
            print(f"  총 결과: {len(results)}개")

            # 상위 3개 결과
            print(f"\n  상위 3개 결과:")
            for i, r in enumerate(results[:3], 1):
                hang_id = r.get('hang_id', 'N/A')
                similarity = r.get('similarity', 0)
                source = r.get('source', 'unknown')
                stages = r.get('stages', [])

                # 제4장::제36조 확인
                is_target = '::제4장::' in hang_id and '::제36조' in hang_id
                marker = "🎯" if is_target else "  "

                print(f"  {marker}{i}. {hang_id}")
                print(f"       유사도: {similarity:.4f} | Source: {source} | Stages: {', '.join(stages)}")

            # 4. 제4장::제36조 순위 확인
            print(f"\n[4] 제4장::제36조 검색 확인")
            jang4_jo36_found = False
            jang4_jo36_rank = None

            for i, r in enumerate(results, 1):
                hang_id = r.get('hang_id', '')
                if '::제4장::' in hang_id and '::제36조' in hang_id:
                    jang4_jo36_found = True
                    jang4_jo36_rank = i
                    print(f"  ✅ 제4장::제36조 발견!")
                    print(f"  순위: {i}위")
                    print(f"  경로: {hang_id}")
                    break

            if not jang4_jo36_found:
                print(f"  ❌ 제4장::제36조 없음 (검색 실패)")

            # 5. 최종 평가
            print("\n" + "=" * 80)
            print("최종 평가")
            print("=" * 80)

            # 성능 목표
            perf_pass = improvement >= 50

            # 품질 목표 (제36조 1~2위)
            quality_pass = jang4_jo36_found and jang4_jo36_rank <= 2

            # A2A 협업 목표
            a2a_pass = a2a_triggered and a2a_count >= 2

            print(f"\n  📋 체크리스트:")
            print(f"    {'✅' if perf_pass else '❌'} 성능: {improvement:.1f}% 개선 (목표: ≥50%)")
            print(f"    {'✅' if quality_pass else '❌'} 품질: 제36조 {jang4_jo36_rank}위 (목표: ≤2위)")
            print(f"    {'✅' if a2a_pass else '❌'} A2A: {a2a_count}개 도메인 협업 (목표: ≥2)")

            all_pass = perf_pass and quality_pass and a2a_pass

            print(f"\n  🏆 종합 결과:")
            if all_pass:
                print(f"    ✅ SUCCESS: 모든 목표 달성!")
                print(f"    Phase 2.0 병렬 A2A 협업 구현 성공")
            else:
                print(f"    ⚠️  PARTIAL: 일부 목표 미달성")
                if not perf_pass:
                    print(f"       - 성능 개선 부족: {improvement:.1f}% < 50%")
                if not quality_pass:
                    print(f"       - 검색 품질 저하: 제36조 {jang4_jo36_rank}위 > 2위")
                if not a2a_pass:
                    print(f"       - A2A 협업 부족: {a2a_count}개 < 2개")

            print("\n" + "=" * 80)

        else:
            print(f"Error: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"\n[Error] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parallel_a2a()
