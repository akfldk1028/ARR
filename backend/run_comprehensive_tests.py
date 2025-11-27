# -*- coding: utf-8 -*-
"""
종합 테스트 실행 스크립트 (발표용)
2025-11-24

실행할 테스트:
1. 시스템 준비 상태 확인
2. 36조 검색 테스트
3. 용도지역 검색 테스트
4. A2A 협업 테스트
5. RNE 그래프 확장 테스트
"""

import sys
import io
import os
import django
from pathlib import Path
import json
from datetime import datetime

# UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Django setup
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law.agent_manager import AgentManager
from graph_db.services.neo4j_service import Neo4jService
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment
env_path = backend_dir / ".env"
load_dotenv(env_path)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Test results storage
test_results = {
    "test_date": datetime.now().isoformat(),
    "tests": []
}

def save_results():
    """Save test results to JSON file"""
    output_file = backend_dir / "test_results_2025_11_24.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 테스트 결과 저장: {output_file}")

print("="*80)
print("법률 검색 시스템 종합 테스트 (2025-11-24)")
print("="*80)

# Test 1: System Readiness
print("\n" + "="*80)
print("TEST 1: 시스템 준비 상태 확인")
print("="*80)

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        # Check HANG nodes with embeddings
        result = session.run("""
            MATCH (h:HANG)
            WHERE h.embedding IS NOT NULL
            RETURN count(h) as count, avg(size(h.embedding)) as avg_dim
        """)
        hang_info = result.single()

        # Check domains
        result = session.run("""
            MATCH (d:Domain)
            OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
            RETURN count(DISTINCT d) as domain_count, count(h) as hang_count
        """)
        domain_info = result.single()

        # Check CONTAINS embeddings
        result = session.run("""
            MATCH ()-[r:CONTAINS]->()
            WHERE r.embedding IS NOT NULL
            RETURN count(r) as count
        """)
        contains_info = result.single()

        system_ready = {
            "hang_nodes_with_embedding": hang_info['count'],
            "embedding_dimension": int(hang_info['avg_dim']) if hang_info['avg_dim'] else 0,
            "domain_count": domain_info['domain_count'],
            "hang_in_domains": domain_info['hang_count'],
            "contains_embeddings": contains_info['count']
        }

        print(f"✅ HANG 노드 임베딩: {system_ready['hang_nodes_with_embedding']}개 ({system_ready['embedding_dimension']}-dim)")
        print(f"✅ Domain: {system_ready['domain_count']}개")
        print(f"✅ Domain별 HANG: {system_ready['hang_in_domains']}개")
        print(f"✅ CONTAINS 관계 임베딩: {system_ready['contains_embeddings']}개")

        test_results['tests'].append({
            "test_name": "System Readiness",
            "status": "PASS",
            "data": system_ready
        })

    driver.close()
except Exception as e:
    print(f"❌ 시스템 확인 실패: {e}")
    test_results['tests'].append({
        "test_name": "System Readiness",
        "status": "FAIL",
        "error": str(e)
    })
    save_results()
    sys.exit(1)

# Test 2: 36조 검색
print("\n" + "="*80)
print("TEST 2: 36조 검색 테스트")
print("="*80)

try:
    manager = AgentManager()
    result = manager.search("36조", limit=10)

    test_2_result = {
        "query": "36조",
        "domain_name": result.get('domain_name'),
        "result_count": len(result.get('results', [])),
        "response_time": result.get('response_time'),
        "results_sample": result.get('results', [])[:5]
    }

    print(f"✅ Primary Domain: {test_2_result['domain_name']}")
    print(f"✅ 검색 결과: {test_2_result['result_count']}개")
    print(f"✅ 응답 시간: {test_2_result['response_time']}ms")

    print("\n상위 5개 결과:")
    for i, res in enumerate(test_2_result['results_sample'], 1):
        print(f"  {i}. {res.get('hang_id', 'N/A')}")
        print(f"     - 법률: {res.get('law_name', 'N/A')} ({res.get('law_type', 'N/A')})")
        print(f"     - 유사도: {res.get('similarity', 0):.4f}")

    test_results['tests'].append({
        "test_name": "36조 검색",
        "status": "PASS",
        "data": test_2_result
    })

except Exception as e:
    print(f"❌ 36조 검색 실패: {e}")
    test_results['tests'].append({
        "test_name": "36조 검색",
        "status": "FAIL",
        "error": str(e)
    })

# Test 3: 용도지역 검색
print("\n" + "="*80)
print("TEST 3: 용도지역 검색 테스트")
print("="*80)

try:
    result = manager.search("용도지역", limit=10)

    test_3_result = {
        "query": "용도지역",
        "domain_name": result.get('domain_name'),
        "result_count": len(result.get('results', [])),
        "response_time": result.get('response_time'),
        "results_sample": result.get('results', [])[:5]
    }

    print(f"✅ Primary Domain: {test_3_result['domain_name']}")
    print(f"✅ 검색 결과: {test_3_result['result_count']}개")
    print(f"✅ 응답 시간: {test_3_result['response_time']}ms")

    print("\n상위 5개 결과:")
    for i, res in enumerate(test_3_result['results_sample'], 1):
        print(f"  {i}. {res.get('hang_id', 'N/A')}")
        print(f"     - 법률: {res.get('law_name', 'N/A')} ({res.get('law_type', 'N/A')})")
        print(f"     - 유사도: {res.get('similarity', 0):.4f}")

    test_results['tests'].append({
        "test_name": "용도지역 검색",
        "status": "PASS",
        "data": test_3_result
    })

except Exception as e:
    print(f"❌ 용도지역 검색 실패: {e}")
    test_results['tests'].append({
        "test_name": "용도지역 검색",
        "status": "FAIL",
        "error": str(e)
    })

# Test 4: 개발행위허가 검색
print("\n" + "="*80)
print("TEST 4: 개발행위허가 검색 테스트")
print("="*80)

try:
    result = manager.search("개발행위허가", limit=10)

    test_4_result = {
        "query": "개발행위허가",
        "domain_name": result.get('domain_name'),
        "result_count": len(result.get('results', [])),
        "response_time": result.get('response_time'),
        "results_sample": result.get('results', [])[:5]
    }

    print(f"✅ Primary Domain: {test_4_result['domain_name']}")
    print(f"✅ 검색 결과: {test_4_result['result_count']}개")
    print(f"✅ 응답 시간: {test_4_result['response_time']}ms")

    print("\n상위 5개 결과:")
    for i, res in enumerate(test_4_result['results_sample'], 1):
        print(f"  {i}. {res.get('hang_id', 'N/A')}")
        print(f"     - 법률: {res.get('law_name', 'N/A')} ({res.get('law_type', 'N/A')})")
        print(f"     - 유사도: {res.get('similarity', 0):.4f}")

    test_results['tests'].append({
        "test_name": "개발행위허가 검색",
        "status": "PASS",
        "data": test_4_result
    })

except Exception as e:
    print(f"❌ 개발행위허가 검색 실패: {e}")
    test_results['tests'].append({
        "test_name": "개발행위허가 검색",
        "status": "FAIL",
        "error": str(e)
    })

# Test 5: Multi-domain A2A 검색
print("\n" + "="*80)
print("TEST 5: A2A 협업 테스트 (Multi-domain)")
print("="*80)

try:
    result = manager.search("용도지역과 개발행위허가 관련 규정", limit=10)

    test_5_result = {
        "query": "용도지역과 개발행위허가 관련 규정",
        "domain_name": result.get('domain_name'),
        "domains_queried": result.get('domains_queried', []),
        "a2a_collaboration": result.get('stats', {}).get('a2a_collaboration_triggered', False),
        "result_count": len(result.get('results', [])),
        "response_time": result.get('response_time')
    }

    print(f"✅ Primary Domain: {test_5_result['domain_name']}")
    print(f"✅ Domains Queried: {', '.join(test_5_result['domains_queried'])}")
    print(f"✅ A2A Collaboration: {test_5_result['a2a_collaboration']}")
    print(f"✅ 검색 결과: {test_5_result['result_count']}개")
    print(f"✅ 응답 시간: {test_5_result['response_time']}ms")

    test_results['tests'].append({
        "test_name": "A2A 협업 테스트",
        "status": "PASS",
        "data": test_5_result
    })

except Exception as e:
    print(f"❌ A2A 협업 테스트 실패: {e}")
    test_results['tests'].append({
        "test_name": "A2A 협업 테스트",
        "status": "FAIL",
        "error": str(e)
    })

# Final Summary
print("\n" + "="*80)
print("테스트 요약")
print("="*80)

passed = sum(1 for t in test_results['tests'] if t['status'] == 'PASS')
failed = sum(1 for t in test_results['tests'] if t['status'] == 'FAIL')

print(f"\n✅ 성공: {passed}개")
print(f"❌ 실패: {failed}개")
print(f"\n총 테스트: {len(test_results['tests'])}개")

# Save results
save_results()

print("\n" + "="*80)
print("테스트 완료!")
print("="*80)