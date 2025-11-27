"""
법률 시스템 완전 재구축 스크립트

순서:
0. Neo4j 완전 초기화
1. PDF → JSON 파싱
2. JSON → Neo4j 로드
3. HANG 노드 임베딩
4. 관계 임베딩 추가 ← 새로 추가!
5. AgentManager 초기화
6. 전체 검증
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(description, command):
    """명령어 실행 및 결과 출력"""
    print(f"\n{'='*80}")
    print(f"{description}")
    print(f"{'='*80}")
    print(f"실행: {command}")
    print()

    result = subprocess.run(
        command,
        shell=True,
        capture_output=False,  # 실시간 출력
        text=True
    )

    if result.returncode != 0:
        print(f"\n[ERROR] {description} 실패")
        return False

    print(f"\n[OK] {description} 완료")
    return True


def main():
    print("\n" + "=" * 80)
    print("법률 시스템 완전 재구축")
    print("=" * 80)
    print()
    print("이 스크립트는 다음 단계를 순차적으로 실행합니다:")
    print("  Step 0: Neo4j 완전 초기화 (노드 + 인덱스)")
    print("  Step 1: PDF → JSON 파싱")
    print("  Step 2: JSON → Neo4j 로드")
    print("  Step 3: HANG 노드 임베딩 (KR-SBERT 768-dim)")
    print("  Step 4: 관계 임베딩 추가 (OpenAI 3072-dim)")
    print("  Step 5: AgentManager 초기화 (도메인 클러스터링)")
    print("  Step 6: 전체 검증")
    print()

    answer = input("계속 진행하시겠습니까? (yes/no): ")
    if answer.lower() != 'yes':
        print("취소되었습니다.")
        return 1

    # Step 0: 완전 초기화
    if not run_command(
        "Step 0: Neo4j 완전 초기화",
        "python complete_neo4j_reset.py"
    ):
        return 1

    # Step 1-3: 기본 파이프라인 (PDF → Neo4j → 노드 임베딩)
    if not run_command(
        "Step 1-3: PDF 파싱 + Neo4j 로드 + 노드 임베딩",
        "python process_law_full_auto.py"
    ):
        return 1

    # Step 4: 관계 임베딩 추가
    if not run_command(
        "Step 4: 관계 임베딩 추가",
        "python add_relationship_embeddings.py"
    ):
        return 1

    # Step 5: 최종 검증
    print("\n" + "=" * 80)
    print("Step 5: 최종 검증")
    print("=" * 80)
    print()

    verification_script = """
import os
import sys
import django
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

print("최종 시스템 상태:")
print("-" * 80)

queries = {
    'LAW nodes': 'MATCH (n:LAW) RETURN count(n) as c',
    'JO nodes': 'MATCH (n:JO) RETURN count(n) as c',
    'HANG nodes': 'MATCH (n:HANG) RETURN count(n) as c',
    'HANG with embeddings': 'MATCH (h:HANG) WHERE h.embedding IS NOT NULL RETURN count(h) as c',
    'Domain nodes': 'MATCH (d:Domain) RETURN count(d) as c',
    'CONTAINS relationships': 'MATCH ()-[r:CONTAINS]->() RETURN count(r) as c',
    'CONTAINS with embeddings': 'MATCH ()-[r:CONTAINS]->() WHERE r.embedding IS NOT NULL RETURN count(r) as c',
}

for name, query in queries.items():
    result = neo4j.execute_query(query)
    count = result[0]['c'] if result else 0
    print(f"  {name}: {count}")

print()
print("=" * 80)
print("[SUCCESS] 법률 시스템 재구축 완료!")
print("=" * 80)
print()
print("다음 단계:")
print("  - python law/relationship_embedding/step5_create_index_and_test.py")
print("  - python law/relationship_embedding/test_real_law_qa.py")
print()

neo4j.disconnect()
"""

    # 검증 스크립트를 임시 파일로 저장하고 실행
    with open('_temp_verify.py', 'w', encoding='utf-8') as f:
        f.write(verification_script)

    result = subprocess.run("python _temp_verify.py", shell=True)

    # 임시 파일 삭제
    if os.path.exists('_temp_verify.py'):
        os.remove('_temp_verify.py')

    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
