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

with driver.session() as session:
    # 첫 번째 HANG 노드의 모든 속성 확인
    query = "MATCH (h:HANG) RETURN h LIMIT 1"
    result = session.run(query)
    record = result.single()

    if record:
        hang = record['h']
        print("HANG 노드의 속성:")
        print("-" * 60)
        for key in sorted(hang.keys()):
            value = hang[key]
            if isinstance(value, list) and len(value) > 10:
                print(f"  {key:30s}: list (length={len(value)})")
            else:
                value_str = str(value)[:50]
                print(f"  {key:30s}: {value_str}")

    # 임베딩 관련 속성 확인
    print("\n" + "=" * 60)
    print("임베딩 속성 확인:")
    print("=" * 60)

    query = """
    MATCH (h:HANG)
    RETURN
        sum(CASE WHEN h.embedding IS NOT NULL THEN 1 ELSE 0 END) as has_embedding,
        sum(CASE WHEN h.kr_sbert_embedding IS NOT NULL THEN 1 ELSE 0 END) as has_kr_sbert,
        sum(CASE WHEN h.openai_embedding IS NOT NULL THEN 1 ELSE 0 END) as has_openai,
        count(h) as total
    """
    result = session.run(query)
    record = result.single()

    print(f"\n총 HANG 노드: {record['total']}개")
    print(f"  - embedding 속성: {record['has_embedding']}개")
    print(f"  - kr_sbert_embedding 속성: {record['has_kr_sbert']}개")
    print(f"  - openai_embedding 속성: {record['has_openai']}개")

driver.close()
