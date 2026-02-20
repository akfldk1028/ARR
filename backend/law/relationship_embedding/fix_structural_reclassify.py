"""
STRUCTURAL 타입 정밀 재분류
- STRUCTURAL 1475개 중 의미 키워드 있는 것을 REFERENCE로 변경
- 순수 구조적 관계만 STRUCTURAL로 유지
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


def analyze_structural_types():
    """STRUCTURAL 타입 분석"""
    neo4j = Neo4jService()
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("=" * 80)
    print("STRUCTURAL 타입 분석 및 재분류")
    print("=" * 80)
    print()

    # 1. STRUCTURAL 타입 가져오기
    query = """
    MATCH (from)-[r:CONTAINS]->(to)
    WHERE r.semantic_type = 'STRUCTURAL'
      AND r.embedding IS NOT NULL
    RETURN elementId(r) as rel_id,
           from.full_id as from_id,
           to.full_id as to_id,
           r.context as context,
           r.keywords as keywords
    """

    print("[1] STRUCTURAL 타입 로드 중...")
    results = neo4j.execute_query(query)
    print(f"[OK] {len(results)}개 로드")
    print()

    # 2. 의미 키워드로 분류
    SEMANTIC_KEYWORDS = [
        '준용', '참조', '따라', '따르', '의거', '근거',
        '적용', '해당', '규정', '조항'
    ]

    print("[2] 의미 키워드 기반 분류")
    print("-" * 80)

    structural_pure = []  # 순수 구조적 (조항 번호만)
    reference_semantic = []  # 의미적 참조 (키워드 있음)

    for r in results:
        context = r.get('context', '') or ''
        keywords = r.get('keywords', []) or []

        # 키워드 체크
        has_semantic = False
        found_keywords = []

        for kw in SEMANTIC_KEYWORDS:
            if kw in context:
                has_semantic = True
                found_keywords.append(kw)
            # keywords 리스트에도 체크
            if keywords and any(kw in str(k) for k in keywords):
                has_semantic = True
                found_keywords.append(kw)

        if has_semantic:
            reference_semantic.append({
                'rel_id': r['rel_id'],
                'from_id': r['from_id'],
                'to_id': r['to_id'],
                'found_keywords': found_keywords
            })
        else:
            structural_pure.append({
                'rel_id': r['rel_id'],
                'from_id': r['from_id'],
                'to_id': r['to_id']
            })

    print(f"순수 구조적 (STRUCTURAL 유지): {len(structural_pure)}개")
    print(f"의미적 참조 (REFERENCE로 변경): {len(reference_semantic)}개")
    print()

    # 3. 샘플 확인
    print("[3] 재분류 샘플 확인")
    print("-" * 80)
    print("\n[REFERENCE로 변경될 것] (의미 키워드 있음)")
    for i, r in enumerate(reference_semantic[:5], 1):
        print(f"{i}. {r['from_id'][:50]} -> {r['to_id'][:40]}")
        print(f"   키워드: {', '.join(r['found_keywords'][:3])}")

    print("\n[STRUCTURAL 유지] (조항 번호만)")
    for i, r in enumerate(structural_pure[:5], 1):
        print(f"{i}. {r['from_id'][:50]} -> {r['to_id'][:40]}")

    print()

    # 4. 사용자 확인
    print("=" * 80)
    print(f"[확인] {len(reference_semantic)}개를 STRUCTURAL -> REFERENCE로 변경하시겠습니까?")
    print("=" * 80)
    answer = input("진행하려면 'yes' 입력: ")

    if answer.lower() != 'yes':
        print("[CANCEL] 취소되었습니다.")
        neo4j.disconnect()
        return

    # 5. Neo4j 업데이트
    print()
    print("[4] Neo4j 업데이트 중...")
    print("-" * 80)

    update_query = """
    MATCH ()-[r]-()
    WHERE elementId(r) = $rel_id
    SET r.semantic_type = 'REFERENCE'
    """

    updated_count = 0
    for r in reference_semantic:
        try:
            neo4j.execute_query(update_query, {'rel_id': r['rel_id']})
            updated_count += 1

            if updated_count % 100 == 0:
                print(f"  진행: {updated_count}/{len(reference_semantic)}")

        except Exception as e:
            print(f"[ERROR] {r['rel_id']}: {e}")

    print(f"[OK] {updated_count}개 업데이트 완료")
    print()

    # 6. 최종 통계
    print("[5] 최종 타입 분포")
    print("=" * 80)

    stats_query = """
    MATCH ()-[r:CONTAINS]->()
    WHERE r.embedding IS NOT NULL
    RETURN r.semantic_type as type, count(*) as count
    ORDER BY count DESC
    """

    stats = neo4j.execute_query(stats_query)
    total = sum(s['count'] for s in stats)

    for s in stats:
        pct = (s['count'] / total) * 100
        print(f"{s['type']:15s}: {s['count']:5d}개 ({pct:5.1f}%)")

    print()
    print("[SUCCESS] 재분류 완료!")

    neo4j.disconnect()


if __name__ == "__main__":
    analyze_structural_types()
