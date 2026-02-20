"""
전체 자동 실행 스크립트

Step 1부터 Step 5까지 순차적으로 모두 실행합니다.

⚠️ 주의:
- 전체 실행 시간: 약 50-60분
- 충분한 메모리 필요 (8GB 이상 권장)
- OpenAI API 비용 발생 (약 $2-3)
- Neo4j Desktop 실행 필요

실행:
    python run_all.py

또는 특정 단계부터 시작:
    python run_all.py --start-from 3
"""

import os
import sys
import subprocess
import time
from pathlib import Path
import argparse

# 프로젝트 루트로 이동
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

def run_step(step_num, script_name, description):
    """단계 실행"""
    print("\n" + "=" * 80)
    print(f"Step {step_num}: {description}")
    print("=" * 80)

    script_path = Path(__file__).parent / script_name
    start_time = time.time()

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(project_root),
            check=True,
            capture_output=False
        )

        elapsed = time.time() - start_time
        print(f"\n✅ Step {step_num} 완료 (소요 시간: {elapsed/60:.1f}분)")
        return True

    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Step {step_num} 실패 (소요 시간: {elapsed/60:.1f}분)")
        print(f"Exit code: {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌오류: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="법률 시스템 전체 자동 실행")
    parser.add_argument(
        "--start-from",
        type=int,
        default=1,
        choices=[1, 2, 3, 4, 5],
        help="시작할 단계 번호 (기본: 1)"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("법률 시스템 전체 자동 실행")
    print("=" * 80)
    print(f"\n시작 단계: Step {args.start_from}")
    print("예상 총 소요 시간: 약 50-60분")
    print("\n⚠️  주의사항:")
    print("  - Neo4j Desktop이 실행 중이어야 합니다")
    print("  - 충분한 메모리 필요 (8GB 이상)")
    print("  - OpenAI API 비용 발생 (약 $2-3)")
    print("\n계속하려면 Enter 키를 누르세요 (취소: Ctrl+C)")

    try:
        input()
    except KeyboardInterrupt:
        print("\n\n취소되었습니다.")
        sys.exit(0)

    # 전체 실행 단계
    steps = [
        (1, "step1_pdf_to_json.py", "PDF → JSON 변환"),
        (2, "step2_json_to_neo4j.py", "JSON → Neo4j 로드"),
        (3, "step3_add_hang_embeddings.py", "HANG 노드 임베딩 추가"),
        (4, "step4_initialize_domains.py", "Domain 노드 초기화"),
        (5, "step5_run_relationship_embedding.py", "CONTAINS 관계 임베딩 추가"),
    ]

    # 시작 단계 필터링
    steps = [(n, s, d) for n, s, d in steps if n >= args.start_from]

    total_start = time.time()
    success_count = 0

    for step_num, script_name, description in steps:
        success = run_step(step_num, script_name, description)

        if success:
            success_count += 1
        else:
            print("\n" + "=" * 80)
            print(f"❌ 실행 중단: Step {step_num}에서 오류 발생")
            print("=" * 80)
            print(f"\n완료된 단계: {success_count}/{len(steps)}")
            print(f"실패한 단계: Step {step_num}")
            print("\n💡 문제 해결 후 다음 명령으로 재개:")
            print(f"python run_all.py --start-from {step_num}")
            sys.exit(1)

        # 단계 간 잠시 대기
        if step_num < steps[-1][0]:
            time.sleep(2)

    # 전체 완료
    total_elapsed = time.time() - total_start

    print("\n" + "=" * 80)
    print("🎉 전체 파이프라인 완료!")
    print("=" * 80)
    print(f"\n완료된 단계: {success_count}/{len(steps)}")
    print(f"총 소요 시간: {total_elapsed/60:.1f}분")

    print("\n📊 최종 검증:")
    print("  python verify_system.py")

    print("\n📖 다음 단계:")
    print("  - 검색 테스트: from agents.law.agent_manager import AgentManager")
    print("  - Neo4j Browser: http://localhost:7474")
    print("  - 문서: law/SYSTEM_GUIDE.md")

if __name__ == "__main__":
    main()
