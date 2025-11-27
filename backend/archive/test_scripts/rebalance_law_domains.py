"""
도메인 자동 재구성 스크립트

역할:
- 크기 > 500인 도메인 자동 분할
- 크기 < 50인 도메인 자동 병합
- AI가 판단하여 최적 도메인 구성

사용법:
    python rebalance_law_domains.py
"""

import os
import sys
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import logging
from agents.law.agent_manager import AgentManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """메인 실행 함수"""
    print("\n" + "=" * 70)
    print("도메인 자동 재구성 시작")
    print("=" * 70)

    try:
        # AgentManager 초기화
        logger.info("Initializing AgentManager...")
        agent_manager = AgentManager()

        # 현재 도메인 상태 출력
        logger.info("\n[현재 도메인 상태]")
        for domain in agent_manager.domains.values():
            status = ""
            if domain.size() > agent_manager.MAX_AGENT_SIZE:
                status = "⚠️ 분할 필요"
            elif domain.size() < agent_manager.MIN_AGENT_SIZE:
                status = "⚠️ 병합 필요"
            else:
                status = "✅ 적정"

            logger.info(f"  - {domain.domain_name}: {domain.size()} nodes {status}")

        logger.info(f"\n총 {len(agent_manager.domains)}개 도메인")

        # 재구성 실행
        logger.info("\n[재구성 실행]")
        results = agent_manager.rebalance_all_domains()

        # 결과 출력
        print("\n" + "=" * 70)
        print("재구성 완료")
        print("=" * 70)
        print(f"  도메인 변경: {results['domains_before']} → {results['domains_after']}")
        print(f"  분할: {results['domains_split']}개")
        print(f"  병합: {results['domains_merged']}개")

        # 재구성 후 도메인 상태
        print("\n[재구성 후 도메인 상태]")
        for domain in agent_manager.domains.values():
            print(f"  - {domain.domain_name}: {domain.size()} nodes")

        # 상세 액션 로그
        if results['actions']:
            print("\n[상세 액션]")
            for i, action in enumerate(results['actions'], 1):
                if action['type'] == 'split':
                    print(f"  {i}. 분할: {action['original']} ({action['size']} nodes)")
                elif action['type'] == 'merge':
                    print(f"  {i}. 병합: {action['source']} ({action['size']}) → {action['target']}")

        print("\n✅ 성공!")
        return 0

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
