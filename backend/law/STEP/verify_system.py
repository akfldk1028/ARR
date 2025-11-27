"""
시스템 검증 스크립트

전체 법률 시스템이 올바르게 구축되었는지 검증합니다.

실행:
    python verify_system.py

검증 항목:
- Neo4j 연결
- 노드 수 (LAW, JANG, JO, HANG, HO, Domain)
- 관계 수 (CONTAINS, NEXT, CITES, BELONGS_TO_DOMAIN)
- HANG 임베딩 (768-dim)
- CONTAINS 임베딩 (3,072-dim)
- 벡터 인덱스
- Domain 분포
"""

import os
import sys
import django
from pathlib import Path

# 프로젝트 루트 설정
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

# Django 설정
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services import Neo4jService

def print_section(title):
    """섹션 헤더 출력"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def check_connection(neo4j):
    """Neo4j 연결 확인"""
    print_section("1. Neo4j 연결 확인")
    try:
        result = neo4j.execute_query("RETURN 1 as test")
        if result and result[0]['test'] == 1:
            print("✅ Neo4j 연결 성공")
            return True
        else:
            print("❌ Neo4j 연결 실패: 응답 없음")
            return False
    except Exception as e:
        print(f"❌ Neo4j 연결 실패: {e}")
        return False

def check_nodes(neo4j):
    """노드 수 확인"""
    print_section("2. 노드 확인")

    # 전체 노드 수
    result = neo4j.execute_query("MATCH (n) RETURN count(n) as count")
    total = result[0]['count']
    print(f"\n전체 노드: {total}개")

    # 노드 타입별 분포
    query = """
    MATCH (n)
    RETURN labels(n)[0] as node_type, count(n) as count
    ORDER BY count DESC
    """
    results = neo4j.execute_query(query)

    print("\n노드 타입별 분포:")
    print("-" * 40)

    expected = {
        'LAW': 3,
        'HANG': 1477,
        'Domain': 5,
    }

    for row in results:
        node_type = row['node_type']
        count = row['count']
        status = ""

        if node_type in expected:
            if count >= expected[node_type]:
                status = "✅"
            else:
                status = "⚠️"
        else:
            status = "  "

        print(f"{status} {node_type:15s}: {count:5d}개")

    # 검증
    issues = []
    for node_type, expected_count in expected.items():
        found = next((r for r in results if r['node_type'] == node_type), None)
        if not found:
            issues.append(f"{node_type} 노드가 없습니다")
        elif found['count'] < expected_count:
            issues.append(f"{node_type} 노드가 부족합니다 (예상: {expected_count}, 실제: {found['count']})")

    return len(issues) == 0, issues

def check_relationships(neo4j):
    """관계 확인"""
    print_section("3. 관계 확인")

    # 전체 관계 수
    result = neo4j.execute_query("MATCH ()-[r]->() RETURN count(r) as count")
    total = result[0]['count']
    print(f"\n전체 관계: {total}개")

    # 관계 타입별 분포
    query = """
    MATCH ()-[r]->()
    RETURN type(r) as rel_type, count(r) as count
    ORDER BY count DESC
    """
    results = neo4j.execute_query(query)

    print("\n관계 타입별 분포:")
    print("-" * 40)

    expected = {
        'CONTAINS': 3000,  # 최소값
        'BELONGS_TO_DOMAIN': 1477,
    }

    for row in results:
        rel_type = row['rel_type']
        count = row['count']
        status = ""

        if rel_type in expected:
            if count >= expected[rel_type]:
                status = "✅"
            else:
                status = "⚠️"
        else:
            status = "  "

        print(f"{status} {rel_type:25s}: {count:5d}개")

    # 검증
    issues = []
    for rel_type, expected_count in expected.items():
        found = next((r for r in results if r['rel_type'] == rel_type), None)
        if not found:
            issues.append(f"{rel_type} 관계가 없습니다")
        elif found['count'] < expected_count:
            issues.append(f"{rel_type} 관계가 부족합니다 (최소: {expected_count}, 실제: {found['count']})")

    return len(issues) == 0, issues

def check_embeddings(neo4j):
    """임베딩 확인"""
    print_section("4. 임베딩 확인")

    # HANG 노드 임베딩
    query = """
    MATCH (h:HANG)
    WITH count(h) as total,
         sum(CASE WHEN h.embedding IS NOT NULL THEN 1 ELSE 0 END) as embedded
    RETURN total, embedded,
           embedded * 100.0 / total as percentage
    """
    result = neo4j.execute_query(query)[0]

    hang_ok = result['percentage'] == 100.0
    status = "✅" if hang_ok else "⚠️"
    print(f"\n{status} HANG 노드 임베딩:")
    print(f"   - 전체: {result['total']}개")
    print(f"   - 임베딩 있음: {result['embedded']}개")
    print(f"   - 비율: {result['percentage']:.1f}%")

    # CONTAINS 관계 임베딩
    query = """
    MATCH ()-[r:CONTAINS]->()
    WITH count(r) as total,
         sum(CASE WHEN r.embedding IS NOT NULL THEN 1 ELSE 0 END) as embedded
    RETURN total, embedded,
           embedded * 100.0 / total as percentage
    """
    result = neo4j.execute_query(query)[0]

    rel_ok = result['percentage'] >= 90.0  # 90% 이상이면 통과
    status = "✅" if rel_ok else "⚠️"
    print(f"\n{status} CONTAINS 관계 임베딩:")
    print(f"   - 전체: {result['total']}개")
    print(f"   - 임베딩 있음: {result['embedded']}개")
    print(f"   - 비율: {result['percentage']:.1f}%")

    issues = []
    if not hang_ok:
        issues.append("HANG 노드 임베딩이 완전하지 않습니다")
    if not rel_ok:
        issues.append("CONTAINS 관계 임베딩이 부족합니다")

    return len(issues) == 0, issues

def check_indexes(neo4j):
    """벡터 인덱스 확인"""
    print_section("5. 벡터 인덱스 확인")

    query = "SHOW INDEXES"
    results = neo4j.execute_query(query)

    print("\n생성된 인덱스:")
    print("-" * 40)

    expected_indexes = ['hang_embedding', 'contains_embedding']
    found_indexes = []

    for row in results:
        name = row.get('name', 'N/A')
        index_type = row.get('type', 'N/A')
        state = row.get('state', 'N/A')

        status = "✅" if state == 'ONLINE' else "⚠️"
        print(f"{status} {name:30s} ({index_type})")

        if any(exp in name for exp in expected_indexes):
            found_indexes.append(name)

    # 검증
    issues = []
    for expected in expected_indexes:
        if not any(expected in found for found in found_indexes):
            issues.append(f"'{expected}' 인덱스가 없습니다")

    return len(issues) == 0, issues

def check_domains(neo4j):
    """Domain 분포 확인"""
    print_section("6. Domain 분포 확인")

    query = """
    MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
    WITH d.domain_name as domain, count(h) as size
    RETURN domain, size,
           size * 100.0 / 1477 as percentage
    ORDER BY size DESC
    """
    results = neo4j.execute_query(query)

    print("\nDomain별 HANG 노드 분포:")
    print("-" * 60)

    total_assigned = 0
    for row in results:
        domain = row['domain']
        size = row['size']
        percentage = row['percentage']
        total_assigned += size
        print(f"  {domain:40s}: {size:4d}개 ({percentage:5.1f}%)")

    print("-" * 60)
    print(f"  {'전체':40s}: {total_assigned:4d}개")

    # 검증
    issues = []
    if len(results) < 3:
        issues.append(f"Domain이 너무 적습니다 (최소 3개 권장, 실제: {len(results)}개)")
    if total_assigned < 1400:
        issues.append(f"할당되지 않은 HANG 노드가 너무 많습니다 (할당: {total_assigned}/1477)")

    return len(issues) == 0, issues

def main():
    print("=" * 80)
    print("법률 시스템 검증")
    print("=" * 80)

    # Neo4j 연결
    neo4j = Neo4jService()
    try:
        neo4j.connect()
    except Exception as e:
        print(f"\n❌ Neo4j 연결 실패: {e}")
        print("\n💡 문제 해결:")
        print("  - Neo4j Desktop에서 데이터베이스를 시작했는지 확인")
        print("  - .env 파일의 NEO4J_* 환경 변수 확인")
        sys.exit(1)

    # 검증 실행
    checks = [
        ("연결", check_connection),
        ("노드", check_nodes),
        ("관계", check_relationships),
        ("임베딩", check_embeddings),
        ("인덱스", check_indexes),
        ("Domain", check_domains),
    ]

    all_issues = []
    passed_count = 0

    for check_name, check_func in checks:
        success, issues = check_func(neo4j)
        if success:
            passed_count += 1
        else:
            all_issues.extend(issues)

    neo4j.disconnect()

    # 최종 결과
    print_section("최종 결과")

    if passed_count == len(checks):
        print("\n🎉 모든 검증 통과!")
        print(f"   {passed_count}/{len(checks)} 항목 성공")
        print("\n✅ 시스템이 정상적으로 구축되었습니다.")
        print("\n📖 다음 단계:")
        print("  - 검색 테스트: from agents.law.agent_manager import AgentManager")
        print("  - 문서: law/SYSTEM_GUIDE.md")
        return 0
    else:
        print(f"\n⚠️  일부 검증 실패")
        print(f"   성공: {passed_count}/{len(checks)}")
        print(f"   실패: {len(checks) - passed_count}/{len(checks)}")

        if all_issues:
            print("\n🔍 발견된 문제:")
            for i, issue in enumerate(all_issues, 1):
                print(f"   {i}. {issue}")

        print("\n💡 문제 해결:")
        print("  - law/STEP/README.md 참조")
        print("  - 각 단계별로 재실행: python stepN_*.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())
