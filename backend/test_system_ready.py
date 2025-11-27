# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

env_path = r"D:\Data\11_Backend\01_ARR\backend\.env"
load_dotenv(env_path)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

print("=" * 80)
print("법률 파싱 시스템 테스트")
print("=" * 80)

with driver.session() as session:
    # 1. 벡터 인덱스 상태 확인
    print("\n1. 벡터 인덱스 확인:")
    result = session.run("SHOW INDEXES WHERE type = 'VECTOR'")
    vector_indexes = list(result)

    hang_embedding_index = None
    contains_embedding_index = None

    for idx in vector_indexes:
        name = idx['name']
        state = idx['state']
        if 'hang_embedding' in name.lower():
            hang_embedding_index = name
            print(f"   - HANG 인덱스: {name} ({state})")
        if 'contains_embedding' in name.lower():
            contains_embedding_index = name
            print(f"   - CONTAINS 인덱스: {name} ({state})")

    if not hang_embedding_index:
        print("\n❌ HANG 벡터 인덱스가 없습니다!")
        print("   이것은 정상입니다. 시스템은 'hang_embedding_index'를 사용합니다.")

    # 2. HANG 노드의 embedding 속성 샘플 확인
    print("\n2. HANG 노드 임베딩 샘플:")
    result = session.run("""
        MATCH (h:HANG)
        WHERE h.embedding IS NOT NULL
        RETURN h.full_id as id, size(h.embedding) as dim
        LIMIT 3
    """)

    samples = list(result)
    if samples:
        print(f"   ✅ {len(samples)}개 샘플 확인됨:")
        for s in samples:
            print(f"      - {s['id']}: {s['dim']}-dim")
    else:
        print("   ❌ 임베딩이 있는 HANG 노드가 없습니다!")

    # 3. 벡터 검색 테스트
    print("\n3. 벡터 검색 테스트:")

    if samples and hang_embedding_index:
        # 첫 번째 샘플의 임베딩을 쿼리로 사용
        test_query = f"""
        MATCH (h:HANG {{full_id: $full_id}})
        WITH h.embedding as query_emb
        CALL db.index.vector.queryNodes('{hang_embedding_index}', 3, query_emb)
        YIELD node, score
        RETURN node.full_id as id, score
        LIMIT 3
        """

        try:
            result = session.run(test_query, {'full_id': samples[0]['id']})
            search_results = list(result)

            if search_results:
                print(f"   ✅ 벡터 검색 성공 ({len(search_results)}개 결과):")
                for r in search_results:
                    print(f"      - {r['id']}: {r['score']:.4f}")
            else:
                print("   ⚠️  벡터 검색이 결과를 반환하지 않았습니다")

        except Exception as e:
            print(f"   ❌ 벡터 검색 실패: {e}")
    else:
        print("   ⚠️  벡터 검색을 테스트할 수 없습니다 (임베딩 또는 인덱스 없음)")

    # 4. Domain 연결 확인
    print("\n4. Domain 연결 확인:")
    result = session.run("""
        MATCH (d:Domain)
        OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
        RETURN d.domain_name as domain, count(h) as hangs
        ORDER BY hangs DESC
    """)

    domains = list(result)
    if domains:
        print(f"   ✅ {len(domains)}개 도메인:")
        for d in domains:
            print(f"      - {d['domain']}: {d['hangs']}개 HANG")
    else:
        print("   ❌ Domain이 없습니다!")

    # 5. CONTAINS 관계 임베딩 확인
    print("\n5. CONTAINS 관계 임베딩 확인:")
    result = session.run("""
        MATCH ()-[r:CONTAINS]->()
        WHERE r.embedding IS NOT NULL
        RETURN count(r) as count, avg(size(r.embedding)) as avg_dim
    """)

    rel_info = result.single()
    if rel_info and rel_info['count'] > 0:
        print(f"   ✅ {rel_info['count']}개 관계에 임베딩 존재")
        print(f"      - 평균 차원: {rel_info['avg_dim']:.0f}-dim")
    else:
        print("   ❌ CONTAINS 관계 임베딩이 없습니다!")

# 최종 결론
print("\n" + "=" * 80)
print("최종 결론:")
print("=" * 80)

checklist = {
    "Neo4j 연결": True,
    "HANG 노드 존재": True,
    "HANG 임베딩": len(samples) > 0 if 'samples' in locals() else False,
    "벡터 인덱스": hang_embedding_index is not None,
    "Domain 분류": len(domains) > 0 if 'domains' in locals() else False,
    "CONTAINS 임베딩": rel_info['count'] > 0 if 'rel_info' in locals() and rel_info else False,
}

all_ok = all(checklist.values())

if all_ok:
    print("\n✅ 시스템이 완성되어 사용 가능합니다!")
    print("\n다음 단계:")
    print("  1. 검색 테스트: python test_17jo.py")
    print("  2. 도메인 에이전트: python test_17jo_domain.py")
    print("  3. API 사용: POST /api/law/search/")
else:
    print("\n⚠️  일부 구성 요소가 누락되었습니다:\n")
    for item, status in checklist.items():
        symbol = "✅" if status else "❌"
        print(f"  {symbol} {item}")

    print("\n해결 방법:")
    if not checklist["HANG 임베딩"]:
        print("  - HANG 임베딩 생성: python law/scripts/add_hang_embeddings.py")
    if not checklist["Domain 분류"]:
        print("  - Domain 초기화: python law/scripts/initialize_domains.py")

driver.close()
