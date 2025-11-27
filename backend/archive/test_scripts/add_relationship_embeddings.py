"""
관계 임베딩 추가 스크립트
Step 1-4를 순차적으로 실행하여 CONTAINS 관계에 임베딩 추가
"""

import os
import sys
import django
from pathlib import Path

# Django 설정
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService
from src.shared.common_fn import load_embedding_model


def add_relationship_embeddings():
    """관계 임베딩 추가"""

    print("=" * 80)
    print("관계 임베딩 추가")
    print("=" * 80)
    print()

    neo4j = Neo4jService()
    if not neo4j.connect():
        print("[ERROR] Neo4j 연결 실패")
        return 1

    try:
        # [Step 1] 관계 분석
        print("[Step 1] CONTAINS 관계 분석")
        print("-" * 80)

        # CONTAINS 관계 개수 확인
        count_query = """
        MATCH ()-[r:CONTAINS]->()
        RETURN count(r) as total
        """
        result = neo4j.execute_query(count_query)
        total_relationships = result[0]['total']

        print(f"  총 CONTAINS 관계: {total_relationships}개")
        print()

        if total_relationships == 0:
            print("[ERROR] CONTAINS 관계가 없습니다. 먼저 Neo4j 로드를 실행하세요.")
            return 1

        # [Step 2] Context 추출
        print("[Step 2] Context 추출")
        print("-" * 80)

        # Context가 있는 관계 확인
        context_query = """
        MATCH ()-[r:CONTAINS]->()
        WHERE r.context IS NOT NULL
        RETURN count(r) as with_context
        """
        result = neo4j.execute_query(context_query)
        with_context = result[0]['with_context']

        print(f"  Context 있는 관계: {with_context}개")

        if with_context == 0:
            print("[ERROR] Context가 없습니다. 먼저 context를 생성하세요.")
            return 1

        print()

        # [Step 3] 임베딩 생성
        print("[Step 3] OpenAI 임베딩 생성")
        print("-" * 80)

        # 임베딩 모델 로드
        embedding_model, dimension = load_embedding_model("openai")
        print(f"  모델: OpenAI text-embedding-3-large")
        print(f"  차원: {dimension}")
        print()

        # Context 가져오기
        print("  관계 context 로드 중...")
        fetch_query = """
        MATCH (from)-[r:CONTAINS]->(to)
        WHERE r.context IS NOT NULL
        RETURN elementId(r) as rel_id,
               r.context as context
        """

        relationships = neo4j.execute_query(fetch_query)
        print(f"  [OK] {len(relationships)}개 관계 로드")
        print()

        # 임베딩 생성
        print("  임베딩 생성 중...")
        batch_size = 100
        total_batches = (len(relationships) + batch_size - 1) // batch_size

        embeddings_data = []

        for i in range(0, len(relationships), batch_size):
            batch = relationships[i:i + batch_size]
            batch_num = i // batch_size + 1

            print(f"  배치 {batch_num}/{total_batches} ({len(batch)}개)", end=" ")

            # 배치 임베딩 생성
            contexts = [r['context'] for r in batch]

            try:
                batch_embeddings = embedding_model.embed_documents(contexts)

                for j, emb in enumerate(batch_embeddings):
                    embeddings_data.append({
                        'rel_id': batch[j]['rel_id'],
                        'embedding': emb
                    })

                print("[OK]")

            except Exception as e:
                print(f"[ERROR] {e}")
                return 1

        print(f"\n  [OK] {len(embeddings_data)}개 임베딩 생성 완료")
        print()

        # [Step 4] Neo4j 업데이트
        print("[Step 4] Neo4j 업데이트")
        print("-" * 80)

        update_query = """
        MATCH ()-[r]->()
        WHERE elementId(r) = $rel_id
        SET r.embedding = $embedding
        """

        print("  관계 임베딩 업데이트 중...")
        updated = 0

        for i, data in enumerate(embeddings_data, 1):
            try:
                neo4j.execute_query(update_query, {
                    'rel_id': data['rel_id'],
                    'embedding': data['embedding']
                })
                updated += 1

                if i % 500 == 0:
                    print(f"    진행: {i}/{len(embeddings_data)}")

            except Exception as e:
                print(f"[ERROR] {data['rel_id']}: {e}")

        print(f"  [OK] {updated}개 관계 업데이트 완료")
        print()

        # [Step 5] 벡터 인덱스 생성
        print("[Step 5] 벡터 인덱스 생성")
        print("-" * 80)

        # 기존 인덱스 삭제
        try:
            neo4j.execute_query("DROP INDEX contains_embedding IF EXISTS")
            print("  [OK] 기존 인덱스 삭제")
        except:
            pass

        # 새 인덱스 생성
        create_index_query = """
        CREATE VECTOR INDEX contains_embedding IF NOT EXISTS
        FOR ()-[r:CONTAINS]-()
        ON r.embedding
        OPTIONS {
          indexConfig: {
            `vector.dimensions`: $dimension,
            `vector.similarity_function`: 'cosine'
          }
        }
        """

        try:
            neo4j.execute_query(create_index_query, {'dimension': dimension})
            print(f"  [OK] 벡터 인덱스 생성 (dimension: {dimension})")
        except Exception as e:
            print(f"  [ERROR] 인덱스 생성 실패: {e}")

        print()

        # [최종 확인]
        print("[최종 확인]")
        print("=" * 80)

        final_queries = {
            '전체 CONTAINS 관계': 'MATCH ()-[r:CONTAINS]->() RETURN count(r) as c',
            'Context 있는 관계': 'MATCH ()-[r:CONTAINS]->() WHERE r.context IS NOT NULL RETURN count(r) as c',
            'Embedding 있는 관계': 'MATCH ()-[r:CONTAINS]->() WHERE r.embedding IS NOT NULL RETURN count(r) as c',
        }

        for name, query in final_queries.items():
            result = neo4j.execute_query(query)
            count = result[0]['c']
            print(f"  {name}: {count}개")

        print()
        print("=" * 80)
        print("[SUCCESS] 관계 임베딩 추가 완료")
        print("=" * 80)
        print()

        neo4j.disconnect()
        return 0

    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        neo4j.disconnect()
        return 1


if __name__ == "__main__":
    sys.exit(add_relationship_embeddings())
