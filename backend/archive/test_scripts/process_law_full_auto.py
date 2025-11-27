"""
완전 자동 법률 처리 플로우
PDF 파싱 → Neo4j 로드 → 임베딩 생성 → AgentManager 초기화

한 번의 실행으로 모든 작업 완료
"""

import os
import sys
import django
import subprocess
from pathlib import Path

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


def main():
    print("\n" + "=" * 80)
    print("완전 자동 법률 처리 플로우")
    print("=" * 80)

    # 경로 설정
    raw_dir = Path("law/data/raw")
    parsed_dir = Path("law/data/parsed")

    # PDF 파일 목록
    pdfs = [
        "04_국토의 계획 및 이용에 관한 법률(법률)(제19117호)(20230628).pdf",
        "05_국토의 계획 및 이용에 관한 법률 시행령(대통령령)(제33637호)(20230718).pdf",
        "06_국토의 계획 및 이용에 관한 법률 시행규칙(국토교통부령)(제01192호)(20230127).pdf"
    ]

    # Step 0: Neo4j 초기화
    print("\n[Step 0] Neo4j 초기화 중...")
    neo4j = Neo4jService()
    neo4j.connect()

    delete_queries = [
        'MATCH (n:Domain) DETACH DELETE n',
        'MATCH (n:LAW) DETACH DELETE n',
        'MATCH (n:JO) DETACH DELETE n',
        'MATCH (n:HANG) DETACH DELETE n',
        'MATCH (n:HO) DETACH DELETE n',
        'MATCH (n:MOK) DETACH DELETE n',
    ]

    for query in delete_queries:
        neo4j.execute_query(query, {})

    print("[OK] Neo4j 초기화 완료")

    # Step 1: PDF 파싱 (3개)
    print("\n[Step 1] PDF 파싱 중...")
    for pdf in pdfs:
        pdf_path = raw_dir / pdf
        print(f"\n  파싱 중: {pdf}")

        cmd = f'python law/scripts/pdf_to_json.py --pdf "{pdf_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode != 0:
            print(f"[ERROR] 파싱 실패: {pdf}")
            print(result.stderr)
            return 1

    print("[OK] 3개 PDF 파싱 완료")

    # Step 2: Neo4j 로드 (3개 JSON)
    print("\n[Step 2] Neo4j 로드 중...")

    json_files = list(parsed_dir.glob("*.json"))
    print(f"  발견된 JSON 파일: {len(json_files)}개")

    for json_file in json_files:
        print(f"\n  로드 중: {json_file.name}")

        cmd = f'python law/scripts/json_to_neo4j.py --json "{json_file}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')

        if result.returncode != 0:
            print(f"[ERROR] 로드 실패: {json_file.name}")
            print(result.stderr)
            return 1

    print("[OK] 3개 JSON Neo4j 로드 완료")

    # 중간 확인
    print("\n[중간 확인] Neo4j 상태...")
    check_queries = [
        ('LAW nodes', 'MATCH (n:LAW) RETURN count(n) as c'),
        ('JO nodes', 'MATCH (n:JO) RETURN count(n) as c'),
        ('HANG nodes', 'MATCH (n:HANG) RETURN count(n) as c'),
        ('HO nodes', 'MATCH (n:HO) RETURN count(n) as c'),
    ]

    for name, query in check_queries:
        result = neo4j.execute_query(query, {})
        count = result[0]['c']
        print(f"  {name}: {count}")

    # LAW 노드 상세 확인
    print("\n  LAW 노드 상세:")
    law_query = 'MATCH (l:LAW) RETURN l.law_name as name, l.law_type as type ORDER BY type'
    laws = neo4j.execute_query(law_query, {})
    for law in laws:
        print(f"    - {law['name']} ({law['type']})")

    # Step 3: 임베딩 생성
    print("\n[Step 3] HANG 노드 임베딩 생성 중...")
    print("  (KR-SBERT embeddings, 768-dim)")

    cmd = 'python add_kr_sbert_embeddings.py'
    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        print("[ERROR] 임베딩 생성 실패")
        return 1

    print("[OK] 임베딩 생성 완료")

    # Step 4: AgentManager 초기화
    print("\n[Step 4] AgentManager 초기화 중...")
    print("  (자동 도메인 클러스터링)")

    cmd = 'python -c "from agents.law.agent_manager import AgentManager; AgentManager()"'
    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        print("[ERROR] AgentManager 초기화 실패")
        return 1

    print("[OK] AgentManager 초기화 완료")

    # 최종 확인
    print("\n[최종 확인] 시스템 상태...")

    final_queries = [
        ('LAW nodes', 'MATCH (n:LAW) RETURN count(n) as c'),
        ('HANG nodes', 'MATCH (n:HANG) RETURN count(n) as c'),
        ('HANG with embeddings', 'MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h) as c'),
        ('Domain nodes', 'MATCH (d:Domain) RETURN count(d) as c'),
    ]

    for name, query in final_queries:
        result = neo4j.execute_query(query, {})
        count = result[0]['c']
        print(f"  {name}: {count}")

    print("\n" + "=" * 80)
    print("[OK] 완전 자동 처리 완료!")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
