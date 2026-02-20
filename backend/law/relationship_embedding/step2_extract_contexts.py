"""
Step 2: 관계 맥락 텍스트 추출

목적:
- CONTAINS 관계의 from/to 노드 content 추출
- 관계 맥락 텍스트 생성
- 의미 타입 분류
- JSON 파일로 저장
"""

import os
import sys
import django
import json
import re
from pathlib import Path
from typing import Dict, List

# Django 설정
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


# 의미 타입 분류 규칙
SEMANTIC_PATTERNS = {
    'EXCEPTION': [
        r'다만',
        r'제외',
        r'생략',
        r'아니한다',
        r'않는다',
        r'~한 경우',
        r'경우에는',
    ],
    'CONDITION': [
        r'~한 때',
        r'~하는 경우',
        r'적용함에 있어',
        r'~하려는 경우',
    ],
    'DETAIL': [
        r'세부',
        r'구체적',
        r'다음 각',
        r'각 호',
        r'다음과 같다',
    ],
    'REFERENCE': [
        r'제\d+조',
        r'준용',
        r'참조',
        r'따라',
    ],
    'ADDITION': [
        r'또한',
        r'추가',
        r'및',
        r'아울러',
    ]
}


def classify_semantic_type(context: str) -> str:
    """
    관계 맥락 텍스트에서 의미 타입 분류

    Args:
        context: 관계 맥락 텍스트

    Returns:
        의미 타입 ('EXCEPTION', 'CONDITION', 'DETAIL', 'REFERENCE', 'ADDITION', 'GENERAL')
    """
    for sem_type, patterns in SEMANTIC_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, context):
                return sem_type

    return 'GENERAL'


def extract_keywords(text: str) -> List[str]:
    """
    텍스트에서 주요 키워드 추출

    Args:
        text: 입력 텍스트

    Returns:
        키워드 리스트
    """
    keywords = []

    # 패턴 기반 키워드 추출
    all_patterns = []
    for patterns in SEMANTIC_PATTERNS.values():
        all_patterns.extend(patterns)

    for pattern in all_patterns:
        matches = re.findall(pattern, text)
        keywords.extend(matches)

    # 중복 제거
    return list(set(keywords))


def extract_relationship_contexts():
    """관계 맥락 추출 메인 함수"""

    neo4j = Neo4jService()

    print("=" * 80)
    print("Step 2: 관계 맥락 텍스트 추출")
    print("=" * 80)

    # 연결
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[OK] Neo4j 연결 성공\n")

    try:
        # CONTAINS 관계 전체 추출
        print("[1] CONTAINS 관계 추출 중...")
        print("-" * 80)

        query = """
        MATCH (from)-[r:CONTAINS]->(to)
        RETURN
            id(r) as rel_id,
            labels(from)[0] as from_label,
            from.full_id as from_id,
            from.content as from_content,
            labels(to)[0] as to_label,
            to.full_id as to_id,
            to.content as to_content,
            r.order as order
        ORDER BY from_id, order
        """

        results = neo4j.execute_query(query)
        total_count = len(results)

        print(f"  총 {total_count:,d}개 관계 추출\n")

        # 관계 맥락 데이터 생성
        print("[2] 관계 맥락 텍스트 생성 중...")
        print("-" * 80)

        relationship_contexts = []

        for i, record in enumerate(results, 1):
            # 진행 표시
            if i % 500 == 0:
                print(f"  진행: {i:,d} / {total_count:,d} ({i*100/total_count:.1f}%)")

            from_content = record['from_content'] or ""
            to_content = record['to_content'] or ""

            # 부모 끝부분 100자
            from_tail = from_content[-100:] if len(from_content) > 100 else from_content

            # 자식 시작부분 100자
            to_head = to_content[:100] if len(to_content) > 100 else to_content

            # 관계 맥락 텍스트
            context = f"{from_tail} -> {to_head}"

            # 키워드 추출
            keywords = extract_keywords(context)

            # 의미 타입 분류
            semantic_type = classify_semantic_type(context)

            # 데이터 구성
            rel_data = {
                'rel_id': record['rel_id'],
                'from_label': record['from_label'],
                'from_id': record['from_id'],
                'to_label': record['to_label'],
                'to_id': record['to_id'],
                'order': record['order'],
                'from_content': from_content,
                'to_content': to_content,
                'from_tail': from_tail,
                'to_head': to_head,
                'context': context,
                'keywords': keywords,
                'semantic_type': semantic_type
            }

            relationship_contexts.append(rel_data)

        print(f"  완료: {total_count:,d}개 관계 처리\n")

        # 의미 타입 분포 확인
        print("[3] 의미 타입 분포")
        print("-" * 80)

        type_counts = {}
        for rel in relationship_contexts:
            sem_type = rel['semantic_type']
            type_counts[sem_type] = type_counts.get(sem_type, 0) + 1

        for sem_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {sem_type:15s}: {count:6,d}개 ({count*100/total_count:.1f}%)")
        print()

        # 샘플 출력
        print("[4] 샘플 관계 맥락 (각 타입별 1개)")
        print("-" * 80)

        shown_types = set()
        for rel in relationship_contexts:
            sem_type = rel['semantic_type']
            if sem_type not in shown_types:
                print(f"\n  [{sem_type}]")
                print(f"    From: {rel['from_id']}")
                print(f"    To:   {rel['to_id']}")
                print(f"    Context: {rel['context'][:100]}...")
                print(f"    Keywords: {rel['keywords']}")
                shown_types.add(sem_type)

                if len(shown_types) >= 5:
                    break
        print()

        # JSON 파일로 저장
        print("[5] JSON 파일 저장")
        print("-" * 80)

        output_dir = Path(__file__).parent / "data"
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / "relationship_contexts.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(relationship_contexts, f, ensure_ascii=False, indent=2)

        print(f"  파일: {output_file}")
        print(f"  크기: {output_file.stat().st_size / 1024:.1f} KB")
        print(f"  개수: {len(relationship_contexts):,d}개\n")

        # 요약
        print("[6] 요약")
        print("=" * 80)
        print(f"  총 관계 개수: {total_count:,d}개")
        print(f"  파일 저장: {output_file}")
        print()
        print("  다음 단계:")
        print("  -> Step 3: 임베딩 생성 (step3_generate_embeddings.py)")
        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        neo4j.disconnect()
        print("\n[OK] Neo4j 연결 종료")


if __name__ == "__main__":
    extract_relationship_contexts()
