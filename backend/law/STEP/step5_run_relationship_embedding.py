"""
Step 5: CONTAINS 관계 임베딩 추가

CONTAINS 관계에 OpenAI 임베딩을 추가하여 의미 기반 관계 검색을 가능하게 합니다.

실행:
    python step5_run_relationship_embedding.py

처리 시간:
    약 30분 (3,565개 관계)

생성:
    - CONTAINS 관계 임베딩 (3,072차원)
    - contains_embedding 벡터 인덱스
"""

import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트로 이동
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

print("=" * 80)
print("Step 5: CONTAINS 관계 임베딩 추가")
print("=" * 80)

# 관계 임베딩 스크립트 경로
rel_emb_dir = project_root / "law" / "relationship_embedding"

if not rel_emb_dir.exists():
    print(f"❌ 오류: 디렉토리를 찾을 수 없습니다: {rel_emb_dir}")
    sys.exit(1)

scripts = [
    ("step1_analyze_relationships.py", "관계 분석"),
    ("step2_extract_contexts.py", "컨텍스트 추출"),
    ("step3_generate_embeddings.py", "임베딩 생성 (⏱️ 약 20분)"),
    ("step4_update_neo4j.py", "Neo4j 업데이트"),
    ("step5_create_index_and_test.py", "인덱스 생성 및 테스트"),
]

print(f"\n📂 작업 디렉토리: {rel_emb_dir}")
print(f"📄 실행할 스크립트: {len(scripts)}개")
print("⏱️  예상 총 소요 시간: 약 30분")
print("💰 OpenAI API 비용 발생 (약 $2-3)")
print("-" * 80)

# 각 스크립트 순차 실행
for i, (script_name, description) in enumerate(scripts, 1):
    script_path = rel_emb_dir / script_name

    if not script_path.exists():
        print(f"❌ 오류: 스크립트를 찾을 수 없습니다: {script_path}")
        sys.exit(1)

    print(f"\n[{i}/{len(scripts)}] {description}")
    print(f"실행 중: {script_name}")
    print("-" * 40)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(project_root),
            check=True,
            capture_output=False
        )
        print(f"✅ {script_name} 완료")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ 오류: {script_name} 실행 실패 (exit code: {e.returncode})")
        print("\n💡 문제 해결:")
        print("  - OpenAI API 키 확인")
        print("  - Rate limit 오류 시 잠시 대기 후 재실행")
        print("  - Neo4j 연결 확인")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        sys.exit(1)

print("\n" + "=" * 80)
print("✅ Step 5 완료!")
print("=" * 80)

print("\n📊 Neo4j 확인:")
print("  브라우저에서 http://localhost:7474 접속")
print("\n  다음 쿼리 실행:")
print("  MATCH ()-[r:CONTAINS]->()")
print("  WHERE r.embedding IS NOT NULL")
print("  RETURN count(r) as embedded_relations")
print("\n  인덱스 확인:")
print("  SHOW INDEXES")

print("\n" + "=" * 80)
print("🎉 전체 파이프라인 완료!")
print("=" * 80)
print("\n다음 단계: python verify_system.py (시스템 검증)")
