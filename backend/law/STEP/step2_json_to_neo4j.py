"""
Step 2: JSON → Neo4j 로드

표준 JSON 파일을 Neo4j 그래프 데이터베이스에 로드합니다.

실행:
    python step2_json_to_neo4j.py

생성:
    - LAW, JANG, JEOL, JO, HANG, HO 노드
    - CONTAINS, NEXT, CITES 관계
"""

import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트로 이동
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

print("=" * 80)
print("Step 2: JSON → Neo4j 로드")
print("=" * 80)

# 원본 스크립트 경로
script_path = project_root / "law" / "scripts" / "json_to_neo4j.py"

if not script_path.exists():
    print(f"❌ 오류: 스크립트를 찾을 수 없습니다: {script_path}")
    sys.exit(1)

# JSON 파일 확인
parsed_dir = project_root / "law" / "data" / "parsed"
json_files = list(parsed_dir.glob("*.json"))

if not json_files:
    print("❌ 오류: JSON 파일이 없습니다.")
    print("먼저 Step 1을 실행하세요: python step1_pdf_to_json.py")
    sys.exit(1)

print(f"\n📂 발견된 JSON 파일: {len(json_files)}개")
for f in json_files:
    print(f"  - {f.name}")

print(f"\n📄 실행 중: {script_path}")
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
    print("✅ Step 2 완료!")
    print("=" * 80)

    print("\n📊 Neo4j 확인:")
    print("  브라우저에서 http://localhost:7474 접속")
    print("\n  다음 쿼리 실행:")
    print("  MATCH (n) RETURN labels(n)[0] as type, count(n) as count")

except subprocess.CalledProcessError as e:
    print(f"\n❌ 오류: 스크립트 실행 실패 (exit code: {e.returncode})")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ 오류: {e}")
    sys.exit(1)

print("\n다음 단계: python step3_add_hang_embeddings.py")
