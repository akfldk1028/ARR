"""
Step 1: PDF → JSON 변환

법률 PDF 파일을 표준 JSON 포맷으로 파싱합니다.

실행:
    python step1_pdf_to_json.py

출력:
    law/data/parsed/*.json
"""

import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트로 이동
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

print("=" * 80)
print("Step 1: PDF → JSON 변환")
print("=" * 80)

# 원본 스크립트 경로
script_path = project_root / "law" / "scripts" / "pdf_to_json.py"

if not script_path.exists():
    print(f"❌ 오류: 스크립트를 찾을 수 없습니다: {script_path}")
    sys.exit(1)

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
    print("✅ Step 1 완료!")
    print("=" * 80)

    # 생성된 파일 확인
    parsed_dir = project_root / "law" / "data" / "parsed"
    if parsed_dir.exists():
        json_files = list(parsed_dir.glob("*.json"))
        print(f"\n📂 생성된 JSON 파일: {len(json_files)}개")
        for f in json_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  - {f.name} ({size_mb:.2f} MB)")

except subprocess.CalledProcessError as e:
    print(f"\n❌ 오류: 스크립트 실행 실패 (exit code: {e.returncode})")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ 오류: {e}")
    sys.exit(1)

print("\n다음 단계: python step2_json_to_neo4j.py")
