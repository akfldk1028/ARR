"""
Step 4: Domain 노드 초기화 ⭐ 필수!

K-means 클러스터링으로 HANG 노드를 도메인으로 그룹화하고
Neo4j에 Domain 노드와 BELONGS_TO_DOMAIN 관계를 생성합니다.

실행:
    python step4_initialize_domains.py

생성:
    - Domain 노드 (약 5개)
    - BELONGS_TO_DOMAIN 관계 (1,477개)
    - DomainAgent 인스턴스
"""

import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트로 이동
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

print("=" * 80)
print("Step 4: Domain 노드 초기화")
print("=" * 80)

# 원본 스크립트 경로
script_path = project_root / "law" / "scripts" / "initialize_domains.py"

if not script_path.exists():
    print(f"❌ 오류: 스크립트를 찾을 수 없습니다: {script_path}")
    sys.exit(1)

print(f"\n📄 실행 중: {script_path}")
print("⏱️  예상 소요 시간: 약 5분")
print("🔬 K-means 클러스터링 + LLM 도메인 이름 생성")
print("-" * 80)

# 원본 스크립트 실행
try:
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(project_root),
        check=True,
        capture_output=False
    )

    print("\n" + "=" * 80)
    print("✅ Step 4 완료!")
    print("=" * 80)

    print("\n📊 Neo4j 확인:")
    print("  브라우저에서 http://localhost:7474 접속")
    print("\n  다음 쿼리 실행:")
    print("  MATCH (d:Domain) RETURN count(d) as domain_count")
    print("\n  도메인별 분포:")
    print("  MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)")
    print("  RETURN d.domain_name, count(h) as size")
    print("  ORDER BY size DESC")

except subprocess.CalledProcessError as e:
    print(f"\n❌ 오류: 스크립트 실행 실패 (exit code: {e.returncode})")
    print("\n💡 문제 해결:")
    print("  - Step 3 완료 확인: HANG 노드에 임베딩이 있어야 함")
    print("  - OpenAI API 키 확인: 도메인 이름 생성에 필요")
    print("  - Neo4j 연결 확인")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ 오류: {e}")
    sys.exit(1)

print("\n다음 단계: python step5_run_relationship_embedding.py")
