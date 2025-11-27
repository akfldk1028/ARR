"""
용도지역 검색 테스트 스크립트

목적:
1. "용도지역" 쿼리로 API 테스트
2. 몇 조가 검색되는지 확인 (기댓값: 제4장::제36조)
3. 몇 개 노드가 반환되는지 확인
4. A2A 협업 발동 여부 확인
5. JO 레벨 검색 포함 여부 확인 (stage: 'jo_vector')
"""

import requests
import json
from pathlib import Path

API_URL = "http://127.0.0.1:8000/agents/law/api/search"

def test_yongdo_search():
    """용도지역 검색 테스트"""

    print("=" * 80)
    print("용도지역 검색 테스트")
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
        response = requests.post(API_URL, json=payload, timeout=60)

        print(f"\n[Response]")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # 결과 저장
            output_path = Path(__file__).parent / "yongdo_search_results.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"Response saved to: {output_path}")

            # 분석
            print("\n" + "=" * 80)
            print("결과 분석")
            print("=" * 80)

            # 1. 총 결과 개수
            results = data.get('results', [])
            print(f"\n[1] 총 검색 결과: {len(results)}개 노드")

            # 2. 상위 3개 결과 분석
            print(f"\n[2] 상위 3개 결과:")
            for i, result in enumerate(results[:3], 1):
                hang_id = result.get('hang_id', 'N/A')
                content = result.get('content', 'N/A')
                unit_path = result.get('unit_path', 'N/A')
                stage = result.get('stage', 'N/A')
                similarity = result.get('similarity', 0)

                # 조 번호 추출
                jo_number = "알 수 없음"
                if '::제' in hang_id and '조' in hang_id:
                    parts = hang_id.split('::')
                    for part in parts:
                        if part.startswith('제') and '조' in part:
                            jo_number = part
                            break

                # 장 번호 추출
                jang_number = "알 수 없음"
                if '::제' in hang_id and '장::' in hang_id:
                    parts = hang_id.split('::')
                    for part in parts:
                        if part.startswith('제') and '장' in part:
                            jang_number = part
                            break

                print(f"\n  {i}위:")
                print(f"    조 번호: {jo_number}")
                print(f"    장: {jang_number}")
                print(f"    검색 단계: {stage}")
                print(f"    유사도: {similarity:.4f}")
                print(f"    전체 경로: {hang_id}")
                print(f"    내용 (처음 100자): {content[:100]}...")

            # 3. 제4장::제36조 확인
            print(f"\n[3] 제4장::제36조 검색 확인:")
            jang4_jo36_found = False
            jang4_jo36_rank = None

            for i, result in enumerate(results, 1):
                hang_id = result.get('hang_id', '')
                if '::제4장::' in hang_id and '::제36조' in hang_id:
                    jang4_jo36_found = True
                    jang4_jo36_rank = i
                    print(f"  ✓ 제4장::제36조 발견!")
                    print(f"  순위: {i}위")
                    print(f"  경로: {hang_id}")
                    break

            if not jang4_jo36_found:
                print(f"  ✗ 제4장::제36조 없음 (검색 실패)")

            # 4. 제12장 결과 확인
            print(f"\n[4] 제12장(부칙) 결과 확인:")
            jang12_results = [r for r in results if '::제12장::' in r.get('hang_id', '')]

            if jang12_results:
                print(f"  제12장 결과: {len(jang12_results)}개")
                for r in jang12_results[:3]:
                    idx = results.index(r) + 1
                    print(f"    #{idx}: {r.get('hang_id', 'N/A')}")
            else:
                print(f"  제12장 결과 없음 (필터링 성공)")

            # 5. JO 레벨 검색 확인
            print(f"\n[5] JO 레벨 검색 포함 여부:")
            jo_results = [r for r in results if r.get('stage') == 'jo_vector']

            if jo_results:
                print(f"  ✓ JO 레벨 검색 포함: {len(jo_results)}개")
                for r in jo_results[:3]:
                    idx = results.index(r) + 1
                    print(f"    #{idx}: {r.get('hang_id', 'N/A')}")
            else:
                print(f"  ✗ JO 레벨 검색 없음")

            # 6. A2A 협업 확인
            print(f"\n[6] A2A 협업 발동 여부:")
            metadata = data.get('metadata', {})
            collaboration = metadata.get('collaboration', {})

            if collaboration:
                print(f"  ✓ A2A 협업 발동")
                print(f"    협업 도메인 수: {len(collaboration.get('domains', []))}")
                for domain_name, domain_data in collaboration.get('domains', {}).items():
                    result_count = len(domain_data.get('results', []))
                    print(f"    - {domain_name}: {result_count}개 결과")
            else:
                print(f"  ✗ A2A 협업 없음 (단일 도메인 처리)")

            # 7. 최종 평가
            print("\n" + "=" * 80)
            print("최종 평가")
            print("=" * 80)

            if jang4_jo36_found and jang4_jo36_rank == 1:
                print("✓ SUCCESS: 제4장::제36조가 1위로 검색됨!")
            elif jang4_jo36_found:
                print(f"△ PARTIAL: 제4장::제36조가 {jang4_jo36_rank}위로 검색됨 (1위 기대)")
            else:
                print("✗ FAIL: 제4장::제36조가 검색되지 않음")

            print("\n" + "=" * 80)

        else:
            print(f"Error: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"\n[Error] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_yongdo_search()
