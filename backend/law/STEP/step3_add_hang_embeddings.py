"""
Step 3: HANG 노드 임베딩 추가

OpenAI text-embedding-3-large 모델을 사용하여 HANG 노드에 3072차원 임베딩을 추가합니다.

⚠️ 요구사항: OPENAI_API_KEY 환경변수 필요 (API 비용 발생)

실행:
    python step3_add_hang_embeddings.py

처리 시간:
    약 10분 (1,477개 노드)
"""

import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트로 이동
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

print("=" * 80)
print("Step 3: HANG 노드 임베딩 추가")
print("=" * 80)

# 원본 스크립트 경로
script_path = project_root / "law" / "scripts" / "add_hang_embeddings.py"

if not script_path.exists():
    print(f"❌ 오류: 스크립트를 찾을 수 없습니다: {script_path}")
    sys.exit(1)

print(f"\n📄 실행 중: {script_path}")
print("⏱️  예상 소요 시간: 약 10분")
print("🔄 OpenAI text-embedding-3-large (3072-dim)")
print("⚠️  OPENAI_API_KEY 환경변수 필요")
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
    print("✅ Step 3 완료!")
    print("=" * 80)

    print("\n📊 Neo4j 확인:")
    print("  브라우저에서 http://localhost:7474 접속")
    print("\n  다음 쿼리 실행:")
    print("  MATCH (h:HANG)")
    print("  WHERE h.embedding IS NOT NULL")
    print("  RETURN count(h) as embedded_count")

except subprocess.CalledProcessError as e:
    print(f"\n❌ 오류: 스크립트 실행 실패 (exit code: {e.returncode})")
    print("\n💡 문제 해결:")
    print("  - Neo4j가 실행 중인지 확인")
    print("  - 메모리가 충분한지 확인 (8GB 이상 권장)")
    print("  - Step 2가 완료되었는지 확인")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ 오류: {e}")
    sys.exit(1)

print("\n다음 단계: python step4_initialize_domains.py")
