"""
Step 8: REFERENCE 타입 분석 및 재분류

목적:
- REFERENCE 타입 관계 샘플 분석
- 구조적 포함 vs 의미적 참조 구분
- 재분류 기준 수립
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


def analyze_reference_type():
    """REFERENCE 타입 분석 메인 함수"""

    print("=" * 80)
    print("Step 8: REFERENCE 타입 분석")
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
        # REFERENCE 타입 샘플 조회
        print("[2] REFERENCE 타입 샘플 분석 (20개)")
        print("-" * 80)
        print()

        query = """
        MATCH (from)-[r:CONTAINS]->(to)
        WHERE r.semantic_type = 'REFERENCE'
        RETURN
            labels(from)[0] as from_label,
            from.full_id as from_id,
            labels(to)[0] as to_label,
            to.full_id as to_id,
            r.context as context,
            r.keywords as keywords
        LIMIT 20
        """

        results = neo4j.execute_query(query)

        if not results:
            print("  [WARNING] REFERENCE 타입 관계 없음")
            return

        # 패턴 분석
        structural_count = 0
        semantic_count = 0

        semantic_keywords = ['준용', '참조', '따라', '의거', '근거', '적용']

        for i, r in enumerate(results, 1):
            from_label = r['from_label']
            to_label = r['to_label']
            context = r['context'] or ""
            keywords = r['keywords'] or []

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
                classification = "STRUCTURAL"
                structural_count += 1
            else:
                classification = "SEMANTIC"
                semantic_count += 1

            print(f"  #{i}: {from_label} -> {to_label}")
            print(f"    분류: {classification}")
            print(f"    Context: {context[:100]}...")
            print(f"    Keywords: {keywords}")
            print()

        print()
        print(f"  구조적 (STRUCTURAL): {structural_count}개")
        print(f"  의미적 (SEMANTIC/REFERENCE): {semantic_count}개")
        print()

        # 전체 REFERENCE 타입 분포
        print("[3] 전체 REFERENCE 타입 레이블 분포")
        print("-" * 80)

        label_query = """
        MATCH (from)-[r:CONTAINS]->(to)
        WHERE r.semantic_type = 'REFERENCE'
        RETURN
            labels(from)[0] as from_label,
            labels(to)[0] as to_label,
            count(r) as count
        ORDER BY count DESC
        """

        label_results = neo4j.execute_query(label_query)

        print()
        print(f"  {'From':10s} -> {'To':10s} | {'개수':>6s}")
        print(f"  {'-'*10}    {'-'*10}   {'-'*6}")

        for lr in label_results:
            from_lbl = lr['from_label']
            to_lbl = lr['to_label']
            count = lr['count']
            print(f"  {from_lbl:10s} -> {to_lbl:10s} | {count:6,d}")

        print()

        # 재분류 제안
        print("[4] 재분류 제안")
        print("=" * 80)
        print()
        print("  현재 REFERENCE: 1,771개 (49.7%)")
        print()
        print("  재분류 기준:")
        print("  1. 부모-자식 레이블 + 의미 키워드 없음 → STRUCTURAL")
        print("  2. 교차 참조 또는 의미 키워드 있음 → REFERENCE 유지")
        print()
        print("  의미 키워드: 준용, 참조, 따라, 의거, 근거, 적용")
        print()
        print("  예상 결과:")
        print(f"    STRUCTURAL: ~{int(structural_count / 20 * 1771)}개 (추정)")
        print(f"    REFERENCE: ~{int(semantic_count / 20 * 1771)}개 (추정)")
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
    analyze_reference_type()
