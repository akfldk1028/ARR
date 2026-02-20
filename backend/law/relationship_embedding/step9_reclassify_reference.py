"""
Step 9: REFERENCE 타입 재분류

목적:
- REFERENCE 타입 관계 재분류 (STRUCTURAL vs SEMANTIC)
- 구조적 포함 관계를 STRUCTURAL로 재분류
- 의미적 참조 관계만 REFERENCE 유지
"""

import os
import sys
import django
from pathlib import Path

# Django 설정
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


def reclassify_reference_relationships():
    """REFERENCE 관계 재분류 메인 함수"""

    print("=" * 80)
    print("Step 9: REFERENCE -> STRUCTURAL 재분류")
    print("=" * 80)
    print()

    # Neo4j 연결
    neo4j = Neo4jService()

    print("[1] Neo4j 연결")
    print("-" * 80)

    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[OK] Neo4j 연결 성공\n")

    try:
        # 재분류 전 통계
        print("[2] 재분류 전 통계")
        print("-" * 80)

        stats_query = """
        MATCH ()-[r:CONTAINS]->()
        WHERE r.semantic_type IS NOT NULL
        RETURN r.semantic_type as type, count(r) as count
        ORDER BY count DESC
        """

        stats_before = neo4j.execute_query(stats_query)

        print()
        print("  현재 분포:")
        total = 0
        for s in stats_before:
            count = s['count']
            type_name = s['type']
            total += count
            percentage = (count / 3565) * 100
            print(f"    {type_name:15s}: {count:5,d}개 ({percentage:5.1f}%)")

        print(f"    {'총계':15s}: {total:5,d}개")
        print()

        # REFERENCE 재분류
        print("[3] REFERENCE 관계 재분류")
        print("-" * 80)
        print()

        # 의미적 참조 키워드
        semantic_keywords = ['준용', '참조', '따라', '의거', '근거', '적용']

        # REFERENCE 타입 관계 조회
        query = """
        MATCH (from)-[r:CONTAINS]->(to)
        WHERE r.semantic_type = 'REFERENCE'
        RETURN
            id(r) as rel_id,
            labels(from)[0] as from_label,
            labels(to)[0] as to_label,
            r.context as context
        """

        results = neo4j.execute_query(query)
        print(f"  REFERENCE 관계 조회: {len(results):,d}개")
        print()

        # 재분류 카운터
        structural_count = 0
        semantic_count = 0
        structural_ids = []

        print("  재분류 진행 중...")
        for i, r in enumerate(results, 1):
            rel_id = r['rel_id']
            from_label = r['from_label']
            to_label = r['to_label']
            context = r['context'] or ""

            # 의미적 참조 키워드 확인
            has_semantic_keyword = any(kw in context for kw in semantic_keywords)

            # 구조적 vs 의미적 판단
            is_structural = (
                # 부모-자식 레이블 조합
                (from_label == 'LAW' and to_label in ['JANG', 'JO']) or
                (from_label == 'JANG' and to_label in ['JEOL', 'JO']) or
                (from_label == 'JEOL' and to_label == 'JO') or
                (from_label == 'JO' and to_label == 'HANG') or
                (from_label == 'HANG' and to_label == 'HO') or
                (from_label == 'HO' and to_label == 'MOK')
            ) and not has_semantic_keyword

            if is_structural:
                structural_count += 1
                structural_ids.append(rel_id)
            else:
                semantic_count += 1

            # 진행 상태 출력 (100개마다)
            if i % 100 == 0:
                print(f"    진행: {i:,d}/{len(results):,d} ({i/len(results)*100:.1f}%)")

        print(f"    완료: {len(results):,d}/{len(results):,d} (100.0%)")
        print()

        print("  재분류 결과:")
        print(f"    STRUCTURAL: {structural_count:,d}개 ({structural_count/len(results)*100:.1f}%)")
        print(f"    REFERENCE (유지): {semantic_count:,d}개 ({semantic_count/len(results)*100:.1f}%)")
        print()

        # Neo4j 업데이트
        print("[4] Neo4j 업데이트")
        print("-" * 80)
        print()

        if structural_ids:
            print(f"  {structural_count:,d}개 관계를 STRUCTURAL로 업데이트 중...")

            # 배치 업데이트
            batch_size = 100
            total_updated = 0

            for i in range(0, len(structural_ids), batch_size):
                batch_ids = structural_ids[i:i+batch_size]

                update_query = """
                UNWIND $rel_ids AS rel_id
                MATCH ()-[r]-()
                WHERE id(r) = rel_id
                SET r.semantic_type = 'STRUCTURAL'
                RETURN count(r) as updated
                """

                result = neo4j.execute_query(update_query, {'rel_ids': batch_ids})
                batch_updated = result[0]['updated'] if result else 0
                total_updated += batch_updated

                # 진행 상태 출력
                progress = min(i + batch_size, len(structural_ids))
                print(f"    진행: {progress:,d}/{len(structural_ids):,d} ({progress/len(structural_ids)*100:.1f}%)")

            print(f"  [OK] {total_updated:,d}개 관계 업데이트 완료")
            print()
        else:
            print("  [INFO] 업데이트할 관계 없음")
            print()

        # 재분류 후 통계
        print("[5] 재분류 후 통계")
        print("=" * 80)

        stats_after = neo4j.execute_query(stats_query)

        print()
        print("  최종 분포:")
        total_after = 0
        for s in stats_after:
            count = s['count']
            type_name = s['type']
            total_after += count
            percentage = (count / 3565) * 100
            print(f"    {type_name:15s}: {count:5,d}개 ({percentage:5.1f}%)")

        print(f"    {'총계':15s}: {total_after:5,d}개")
        print()

        # 변화 요약
        print("  변화 요약:")
        print(f"    REFERENCE: 1,771개 -> {semantic_count:,d}개 (감소: {1771-semantic_count:,d}개)")
        print(f"    STRUCTURAL: 0개 -> {structural_count:,d}개 (신규)")
        print()

        # 새로운 분포 비율
        print("  개선 사항:")
        print("    [이전] REFERENCE가 49.7%로 과다 분류")
        print(f"    [이후] REFERENCE가 {semantic_count/3565*100:.1f}%로 정상화")
        print(f"           STRUCTURAL이 {structural_count/3565*100:.1f}%로 구조적 관계 명확화")
        print()

        print("=" * 80)
        print()
        print("  [SUCCESS] REFERENCE 타입 재분류 완료!")
        print()
        print("  다음 단계:")
        print("    1. Step 7 고급 테스트 재실행")
        print("    2. 패턴 없는 쿼리 정확도 개선 확인")
        print("    3. DomainAgent 통합 준비")
        print()
        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        neo4j.disconnect()
        print("\n[OK] Neo4j 연결 종료")


if __name__ == "__main__":
    reclassify_reference_relationships()
