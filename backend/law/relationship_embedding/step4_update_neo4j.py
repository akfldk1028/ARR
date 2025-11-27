"""
Step 4: Neo4j 관계 업데이트

목적:
- relationship_contexts_with_embeddings.json 로드
- Neo4j CONTAINS 관계에 임베딩 및 메타데이터 추가
- 배치 처리로 성능 최적화
"""

import os
import sys
import django
import json
from pathlib import Path
from typing import List, Dict

# Django 설정
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


def update_relationships_batch(neo4j: Neo4jService, batch: List[Dict]) -> int:
    """
    배치로 관계 업데이트

    Args:
        neo4j: Neo4j 서비스
        batch: 관계 데이터 배치

    Returns:
        성공 개수
    """
    try:
        # 배치 데이터 준비
        rows = []
        for rel in batch:
            rows.append({
                'rel_id': rel['rel_id'],
                'embedding': rel['embedding'],
                'context': rel['context'],
                'semantic_type': rel['semantic_type'],
                'keywords': rel['keywords'],
                'embedding_dim': rel['embedding_dim']
            })

        # 배치 업데이트 쿼리
        query = """
        UNWIND $rows AS row
        MATCH ()-[r]-()
        WHERE id(r) = row.rel_id
        CALL db.create.setRelationshipVectorProperty(r, 'embedding', row.embedding)
        SET r.context = row.context,
            r.semantic_type = row.semantic_type,
            r.keywords = row.keywords,
            r.embedding_dim = row.embedding_dim
        RETURN count(r) as updated_count
        """

        result = neo4j.execute_query(query, {'rows': rows})

        if result and len(result) > 0:
            return result[0]['updated_count']
        else:
            return 0

    except Exception as e:
        print(f"    [ERROR] 배치 업데이트 실패: {e}")
        # 개별 재시도
        success_count = 0
        for rel in batch:
            try:
                single_query = """
                MATCH ()-[r]-()
                WHERE id(r) = $rel_id
                CALL db.create.setRelationshipVectorProperty(r, 'embedding', $embedding)
                SET r.context = $context,
                    r.semantic_type = $semantic_type,
                    r.keywords = $keywords,
                    r.embedding_dim = $embedding_dim
                RETURN count(r) as updated_count
                """
                params = {
                    'rel_id': rel['rel_id'],
                    'embedding': rel['embedding'],
                    'context': rel['context'],
                    'semantic_type': rel['semantic_type'],
                    'keywords': rel['keywords'],
                    'embedding_dim': rel['embedding_dim']
                }
                result = neo4j.execute_query(single_query, params)
                if result and result[0]['updated_count'] > 0:
                    success_count += 1
            except Exception as e2:
                print(f"    [ERROR] 개별 업데이트 실패 (rel_id={rel['rel_id']}): {e2}")

        return success_count


def update_neo4j_relationships():
    """Neo4j 관계 업데이트 메인 함수"""

    print("=" * 80)
    print("Step 4: Neo4j 관계 업데이트")
    print("=" * 80)

    # 입력 파일 로드
    input_file = Path(__file__).parent / "data" / "relationship_contexts_with_embeddings.json"

    if not input_file.exists():
        print(f"[ERROR] 입력 파일 없음: {input_file}")
        print("  -> Step 3을 먼저 실행하세요: python step3_generate_embeddings.py")
        return

    print(f"[1] 입력 파일 로드: {input_file.name}")
    print("-" * 80)

    with open(input_file, 'r', encoding='utf-8') as f:
        relationship_data = json.load(f)

    # 임베딩이 있는 관계만 필터
    relationship_data_with_emb = [rel for rel in relationship_data if 'embedding' in rel]

    total_count = len(relationship_data_with_emb)
    print(f"  총 {total_count:,d}개 관계 (임베딩 포함)\n")

    # Neo4j 연결
    neo4j = Neo4jService()

    print("[2] Neo4j 연결")
    print("-" * 80)

    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return

    print("[OK] Neo4j 연결 성공\n")

    try:
        # 배치 처리 설정
        batch_size = 100
        total_batches = (total_count + batch_size - 1) // batch_size

        print("[3] 관계 업데이트 시작")
        print("-" * 80)
        print(f"  배치 크기: {batch_size}")
        print(f"  총 배치: {total_batches}\n")

        success_count = 0
        fail_count = 0

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_count)
            batch = relationship_data_with_emb[start_idx:end_idx]

            print(f"  배치 {batch_idx + 1}/{total_batches}: {start_idx:,d} ~ {end_idx:,d}")

            # 배치 업데이트
            updated = update_relationships_batch(neo4j, batch)
            success_count += updated
            fail_count += (len(batch) - updated)

            if updated == len(batch):
                print(f"    [OK] {updated}개 업데이트 성공")
            else:
                print(f"    [PARTIAL] {updated}/{len(batch)}개 업데이트 성공")

        print()
        print(f"  완료: {success_count:,d}개 성공, {fail_count:,d}개 실패\n")

        # 검증
        print("[4] 업데이트 검증")
        print("-" * 80)

        verify_query = """
        MATCH ()-[r:CONTAINS]->()
        WHERE r.embedding IS NOT NULL
        RETURN count(r) as count_with_embedding
        """
        result = neo4j.execute_query(verify_query)

        if result:
            count_with_emb = result[0]['count_with_embedding']
            print(f"  임베딩 있는 CONTAINS 관계: {count_with_emb:,d}개")
            print(f"  전체 CONTAINS 관계 대비: {count_with_emb*100/total_count:.1f}%\n")

        # 샘플 확인
        sample_query = """
        MATCH ()-[r:CONTAINS]->()
        WHERE r.embedding IS NOT NULL
        RETURN
            r.semantic_type as semantic_type,
            r.context as context,
            r.keywords as keywords,
            r.embedding_dim as embedding_dim
        LIMIT 5
        """
        samples = neo4j.execute_query(sample_query)

        if samples:
            print("  샘플 관계 (5개):")
            for i, sample in enumerate(samples, 1):
                context = sample['context'][:80] + "..." if len(sample['context']) > 80 else sample['context']
                print(f"    #{i}: [{sample['semantic_type']}]")
                print(f"        Context: {context}")
                print(f"        Keywords: {sample['keywords']}")
                print(f"        Embedding dim: {sample['embedding_dim']}")
        print()

        # 의미 타입별 분포
        type_query = """
        MATCH ()-[r:CONTAINS]->()
        WHERE r.semantic_type IS NOT NULL
        RETURN r.semantic_type as type, count(r) as count
        ORDER BY count DESC
        """
        type_results = neo4j.execute_query(type_query)

        if type_results:
            print("  의미 타입별 분포:")
            for tr in type_results:
                print(f"    {tr['type']:15s}: {tr['count']:6,d}개")
        print()

        # 요약
        print("[5] 요약")
        print("=" * 80)
        print(f"  총 관계: {total_count:,d}개")
        print(f"  업데이트 성공: {success_count:,d}개")
        print(f"  업데이트 실패: {fail_count:,d}개")
        print()
        print("  다음 단계:")
        print("  -> Step 5: 벡터 인덱스 생성 (step5_create_indexes.py)")
        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        neo4j.disconnect()
        print("\n[OK] Neo4j 연결 종료")


if __name__ == "__main__":
    update_neo4j_relationships()
