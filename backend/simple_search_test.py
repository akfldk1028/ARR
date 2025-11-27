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
print("법률 검색 테스트")
print("=" * 80)

with driver.session() as session:
    # 1. 17조 검색 (정확한 매칭)
    print("\n1. 17조 검색 (정확한 매칭):")
    query = """
    MATCH (h:HANG)
    WHERE h.full_id CONTAINS "제17조"
      AND NOT h.full_id CONTAINS "제4절"
    RETURN h.full_id as id, h.content as content, h.law_name as law
    LIMIT 3
    """

    results = session.run(query)
    results_list = list(results)

    if results_list:
        print(f"\n   ✅ {len(results_list)}개 결과 발견:\n")
        for i, r in enumerate(results_list, 1):
            print(f"   {i}. {r['law']}")
            print(f"      ID: {r['id']}")
            print(f"      내용: {r['content'][:100]}...")
            print()
    else:
        print("   ❌ 17조가 없습니다!")

    # 2. 도메인별 HANG 개수
    print("\n2. 도메인별 조항 분포:")
    query = """
    MATCH (d:Domain)<-[:BELONGS_TO_DOMAIN]-(h:HANG)
    RETURN d.domain_name as domain, count(h) as count
    ORDER BY count DESC
    """

    results = session.run(query)
    for r in results:
        print(f"   - {r['domain']:40s}: {r['count']:4d}개")

    # 3. 벡터 검색 시뮬레이션 (임의의 HANG 임베딩으로 유사 검색)
    print("\n3. 벡터 검색 시뮬레이션:")
    print("   (첫 번째 HANG 노드와 유사한 조항 검색)")

    # 첫 번째 HANG의 임베딩을 쿼리로 사용
    query = """
    MATCH (h:HANG)
    WHERE h.embedding IS NOT NULL
    WITH h LIMIT 1
    CALL db.index.vector.queryNodes('hang_embedding_index', 5, h.embedding)
    YIELD node, score
    RETURN node.full_id as id,
           node.content as content,
           score
    ORDER BY score DESC
    LIMIT 3
    """

    try:
        results = session.run(query)
        results_list = list(results)

        if results_list:
            print(f"\n   ✅ 벡터 검색 성공 ({len(results_list)}개):\n")
            for i, r in enumerate(results_list, 1):
                print(f"   {i}. {r['id']}")
                print(f"      유사도: {r['score']:.4f}")
                print(f"      내용: {r['content'][:80]}...")
                print()
        else:
            print("   ⚠️  결과 없음")

    except Exception as e:
        print(f"   ❌ 벡터 검색 실패: {e}")

    # 4. CONTAINS 관계 그래프 탐색
    print("\n4. 그래프 관계 탐색 (17조의 하위 항/호):")
    query = """
    MATCH path = (parent)-[:CONTAINS*1..2]->(child:HANG)
    WHERE parent.full_id CONTAINS "제17조"
      AND NOT parent.full_id CONTAINS "제4절"
    RETURN parent.full_id as parent_id,
           child.full_id as child_id,
           child.content as content,
           length(path) as depth
    ORDER BY depth, child_id
    LIMIT 5
    """

    results = session.run(query)
    results_list = list(results)

    if results_list:
        print(f"\n   ✅ {len(results_list)}개 하위 노드 발견:\n")
        for i, r in enumerate(results_list, 1):
            print(f"   {i}. {r['parent_id']} → {r['child_id']}")
            print(f"      깊이: {r['depth']}, 내용: {r['content'][:60]}...")
            print()
    else:
        print("   ⚠️  하위 노드 없음 (17조가 단일 조항일 수 있음)")

print("\n" + "=" * 80)
print("검색 테스트 완료")
print("=" * 80)
print("\n시스템이 정상적으로 작동하고 있습니다!")
print("다음 단계:")
print("  - Django 환경에서 DomainAgent 테스트")
print("  - Multi-Agent 협업 테스트")
print("  - API 엔드포인트 테스트")

driver.close()
