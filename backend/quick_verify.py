"""
간단한 Neo4j 시스템 검증 스크립트
Django 없이 직접 Neo4j 연결
"""

# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

# .env 파일 로드
env_path = r"D:\Data\11_Backend\01_ARR\backend\.env"
load_dotenv(env_path)

# Neo4j 연결 정보
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def main():
    print("=" * 80)
    print("법률 파싱 시스템 검증")
    print("=" * 80)

    # Neo4j 연결
    print(f"\nNeo4j URI: {NEO4J_URI}")
    print(f"Neo4j User: {NEO4J_USER}")

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("✅ Neo4j 연결 성공")
    except Exception as e:
        print(f"❌ Neo4j 연결 실패: {e}")
        print("\n해결 방법:")
        print("1. Neo4j Desktop에서 데이터베이스가 실행 중인지 확인")
        print("2. .env 파일의 NEO4J_* 환경변수 확인")
        return

    with driver.session() as session:
        # 1. 노드 확인
        print_section("1. 노드 확인")
        result = session.run("MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY count DESC")
        nodes = list(result)

        total_nodes = sum(r['count'] for r in nodes)
        print(f"\n전체 노드: {total_nodes}개\n")

        expected_nodes = {
            'LAW': 3,
            'HANG': 1477,
            'Domain': 5
        }

        for record in nodes:
            node_type = record['type']
            count = record['count']

            status = ""
            if node_type in expected_nodes:
                if count >= expected_nodes[node_type]:
                    status = "✅"
                else:
                    status = "⚠️"
            else:
                status = "  "

            print(f"{status} {node_type:15s}: {count:5d}개")

        # 2. 관계 확인
        print_section("2. 관계 확인")
        result = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC")
        rels = list(result)

        total_rels = sum(r['count'] for r in rels)
        print(f"\n전체 관계: {total_rels}개\n")

        expected_rels = {
            'CONTAINS': 3000,
            'BELONGS_TO_DOMAIN': 1477
        }

        for record in rels:
            rel_type = record['type']
            count = record['count']

            status = ""
            if rel_type in expected_rels:
                if count >= expected_rels[rel_type]:
                    status = "✅"
                else:
                    status = "⚠️"
            else:
                status = "  "

            print(f"{status} {rel_type:25s}: {count:5d}개")

        # 3. HANG 임베딩 확인
        print_section("3. HANG 노드 임베딩 확인")
        query = """
        MATCH (h:HANG)
        WITH count(h) as total,
             sum(CASE WHEN h.kr_sbert_embedding IS NOT NULL THEN 1 ELSE 0 END) as kr_sbert,
             sum(CASE WHEN h.openai_embedding IS NOT NULL THEN 1 ELSE 0 END) as openai
        RETURN total, kr_sbert, openai,
               kr_sbert * 100.0 / total as kr_percentage,
               openai * 100.0 / total as openai_percentage
        """
        result = session.run(query)
        record = result.single()

        total = record['total']
        kr_sbert = record['kr_sbert']
        openai = record['openai']
        kr_pct = record['kr_percentage']
        openai_pct = record['openai_percentage']

        kr_status = "✅" if kr_pct == 100.0 else "⚠️"
        openai_status = "✅" if openai_pct == 100.0 else "⚠️"

        print(f"\n{kr_status} KR-SBERT 임베딩 (768-dim):")
        print(f"   - 전체 HANG: {total}개")
        print(f"   - 임베딩 있음: {kr_sbert}개")
        print(f"   - 비율: {kr_pct:.1f}%")

        print(f"\n{openai_status} OpenAI 임베딩 (3072-dim):")
        print(f"   - 전체 HANG: {total}개")
        print(f"   - 임베딩 있음: {openai}개")
        print(f"   - 비율: {openai_pct:.1f}%")

        # 4. CONTAINS 관계 임베딩 확인
        print_section("4. CONTAINS 관계 임베딩 확인")
        query = """
        MATCH ()-[r:CONTAINS]->()
        WITH count(r) as total,
             sum(CASE WHEN r.embedding IS NOT NULL THEN 1 ELSE 0 END) as embedded
        RETURN total, embedded,
               embedded * 100.0 / total as percentage
        """
        result = session.run(query)
        record = result.single()

        if record:
            total = record['total']
            embedded = record['embedded']
            percentage = record['percentage']

            status = "✅" if percentage >= 90.0 else "⚠️"
            print(f"\n{status} CONTAINS 관계 임베딩:")
            print(f"   - 전체 관계: {total}개")
            print(f"   - 임베딩 있음: {embedded}개")
            print(f"   - 비율: {percentage:.1f}%")
        else:
            print("\n⚠️  CONTAINS 관계가 없습니다")

        # 5. 벡터 인덱스 확인
        print_section("5. 벡터 인덱스 확인")
        result = session.run("SHOW INDEXES")
        indexes = list(result)

        print("\n생성된 인덱스:")

        expected_indexes = ['hang_kr_sbert', 'hang_openai', 'contains_embedding']
        found_indexes = []

        for record in indexes:
            name = record.get('name', 'N/A')
            index_type = record.get('type', 'N/A')
            state = record.get('state', 'N/A')

            status = "✅" if state == 'ONLINE' else "⚠️"
            print(f"{status} {name:30s} ({index_type}) - {state}")

            if any(exp in name for exp in expected_indexes):
                found_indexes.append(name)

        # 6. Domain 분포 확인
        print_section("6. Domain 분포 확인")
        query = """
        MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
        WITH d.domain_name as domain, count(h) as size
        RETURN domain, size,
               size * 100.0 / 1477 as percentage
        ORDER BY size DESC
        """
        result = session.run(query)
        domains = list(result)

        if domains:
            print("\nDomain별 HANG 노드 분포:")
            print("-" * 60)

            total_assigned = 0
            for record in domains:
                domain = record['domain']
                size = record['size']
                percentage = record['percentage']
                total_assigned += size
                print(f"  {domain:40s}: {size:4d}개 ({percentage:5.1f}%)")

            print("-" * 60)
            print(f"  {'전체':40s}: {total_assigned:4d}개")
        else:
            print("\n⚠️  Domain 분류가 없습니다")

        # 최종 결과
        print_section("최종 결과")

        issues = []

        # 노드 검증
        for node_type, expected in expected_nodes.items():
            found = next((r for r in nodes if r['type'] == node_type), None)
            if not found:
                issues.append(f"{node_type} 노드가 없습니다")
            elif found['count'] < expected:
                issues.append(f"{node_type} 노드가 부족합니다 (예상: {expected}, 실제: {found['count']})")

        # 관계 검증
        for rel_type, expected in expected_rels.items():
            found = next((r for r in rels if r['type'] == rel_type), None)
            if not found:
                issues.append(f"{rel_type} 관계가 없습니다")
            elif found['count'] < expected:
                issues.append(f"{rel_type} 관계가 부족합니다 (최소: {expected}, 실제: {found['count']})")

        # 임베딩 검증
        if kr_pct < 100.0:
            issues.append("KR-SBERT 임베딩이 완전하지 않습니다")
        if openai_pct < 100.0:
            issues.append("OpenAI 임베딩이 완전하지 않습니다")

        # 인덱스 검증
        for expected in expected_indexes:
            if not any(expected in found for found in found_indexes):
                issues.append(f"'{expected}' 벡터 인덱스가 없습니다")

        # Domain 검증
        if not domains:
            issues.append("Domain 분류가 없습니다")
        elif len(domains) < 3:
            issues.append(f"Domain이 너무 적습니다 (최소 3개 권장, 실제: {len(domains)}개)")

        if not issues:
            print("\n🎉 모든 검증 통과!")
            print("\n✅ 시스템이 완성되어 사용 가능합니다")
            print("\n📖 다음 단계:")
            print("  1. 검색 테스트: python test_17jo.py")
            print("  2. 도메인 에이전트 테스트: python test_17jo_domain.py")
            print("  3. API 사용: /api/law/search/")
        else:
            print(f"\n⚠️  {len(issues)}개 문제 발견\n")
            for i, issue in enumerate(issues, 1):
                print(f"   {i}. {issue}")

            print("\n💡 문제 해결:")
            print("  - 전체 파이프라인 재실행: python law/STEP/run_all.py")
            print("  - 또는 단계별 실행:")
            print("    1. python law/scripts/pdf_to_json.py")
            print("    2. python law/scripts/json_to_neo4j.py")
            print("    3. python law/scripts/add_hang_embeddings.py")
            print("    4. python law/scripts/initialize_domains.py")

    driver.close()

if __name__ == "__main__":
    main()
