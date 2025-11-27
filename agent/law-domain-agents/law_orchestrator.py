"""
Law Search Orchestrator - A2A Multi-Agent Collaboration

agent/a2a/user-facing-agent 패턴 적용:
- 5개 법률 도메인 에이전트를 RemoteA2aAgent로 등록
- Google ADK Agent with sub_agents로 자동 delegation
- 사용자 질의를 적절한 도메인 에이전트로 라우팅
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "shared"))

import logging
from typing import List
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base URL for agent server
BASE_URL = "http://localhost:8011"

# 5개 법률 도메인 에이전트 slug (서버 로그에서 확인)
DOMAIN_SLUGS = [
    "domain_domain_09b3af0d",  # 국토 계획 및 이용
    "domain_domain_3be25bdc",  # 국토 이용 및 관리
    "domain_domain_fad24752",  # 건축 및 시설
    "domain_domain_c283b545",  # 도시계획 및 개발 사업
    "domain_domain_676e7400",  # 국토 이용 및 건축제한
]


class LawSearchOrchestrator:
    """
    법률 검색 orchestrator

    5개 도메인 에이전트를 RemoteA2aAgent로 등록하고
    사용자 질의를 자동으로 라우팅
    """

    def __init__(self):
        """Orchestrator 초기화"""
        logger.info("="*70)
        logger.info("Law Search Orchestrator - Initializing...")
        logger.info("="*70)

        # Step 1: 도메인 에이전트들을 RemoteA2aAgent로 등록
        self.domain_agents = self._register_domain_agents()

        # Step 2: Orchestrator 에이전트 생성 (sub_agents로 자동 delegation)
        self.orchestrator = self._create_orchestrator()

        # Step 3: Runner 생성 (Google ADK 패턴)
        self.runner = self._create_runner()

        logger.info("✓ Orchestrator ready with %d domain agents", len(self.domain_agents))
        logger.info("="*70)

    def _register_domain_agents(self) -> List[RemoteA2aAgent]:
        """
        도메인 에이전트들을 RemoteA2aAgent로 등록

        agent/a2a/user-facing-agent/agent.py 패턴:
        ```python
        history_agent = RemoteA2aAgent(
            name="HistoryHelperAgent",
            agent_card=f"http://127.0.0.1:8001{AGENT_CARD_WELL_KNOWN_PATH}"
        )
        ```
        """
        logger.info("Registering domain agents as RemoteA2aAgents...")

        agents = []
        for slug in DOMAIN_SLUGS:
            agent_card_url = f"{BASE_URL}/.well-known/agent-card/{slug}.json"

            # RemoteA2aAgent 생성
            agent = RemoteA2aAgent(
                name=f"LawDomainAgent_{slug}",
                description=f"Korean law search agent for domain {slug}",
                agent_card=agent_card_url
            )

            agents.append(agent)
            logger.info(f"  ✓ Registered: {slug}")

        return agents

    def _create_orchestrator(self) -> Agent:
        """
        Orchestrator 에이전트 생성

        agent/a2a/user-facing-agent/agent.py 패턴:
        ```python
        root_agent = Agent(
            name="StudentHelperAgent",
            model=LiteLlm("openai/gpt-4o"),
            sub_agents=[history_agent, philosophy_agent]  # 자동 delegation!
        )
        ```
        """
        logger.info("Creating orchestrator agent...")

        orchestrator = Agent(
            name="LawSearchOrchestrator",
            description="Korean law search orchestrator that delegates to specialized domain agents",
            model=LiteLlm("openai/gpt-4o"),
            sub_agents=self.domain_agents  # 핵심! 자동 delegation
        )

        logger.info("  ✓ Orchestrator created with %d sub-agents", len(self.domain_agents))

        return orchestrator

    def _create_runner(self) -> Runner:
        """
        Runner 생성 (Google ADK 패턴)

        Google ADK 문서 패턴:
        ```python
        runner = Runner(
            app_name="my_app",
            agent=agent,
            session_service=InMemorySessionService()
        )
        ```
        """
        logger.info("Creating runner...")

        runner = Runner(
            app_name="law_search",
            agent=self.orchestrator,
            session_service=InMemorySessionService()
        )

        logger.info("  ✓ Runner created")

        return runner

    async def search(self, query: str, user_id: str = "default", session_id: str = "default") -> str:
        """
        법률 검색 실행

        Google ADK 패턴:
        ```python
        # 세션 생성
        session = await session_service.create_session(
            app_name="my_app", user_id="user123", session_id="session456"
        )
        # 쿼리 실행
        content = types.Content(role='user', parts=[types.Part(text="query")])
        async for event in runner.run_async(
            user_id="user123",
            session_id="session456",
            new_message=content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text)
        ```

        Args:
            query: 사용자 질의
            user_id: 사용자 ID (default: "default")
            session_id: 세션 ID (default: "default")

        Returns:
            검색 결과 (orchestrator가 domain agents와 협업하여 생성)
        """
        logger.info(f"[Orchestrator] Query: {query}")

        # 세션 생성
        session_service = self.runner.session_service
        await session_service.create_session(
            app_name="law_search",
            user_id=user_id,
            session_id=session_id
        )
        logger.info(f"  ✓ Created new session: {session_id}")

        # Content 생성 (Google ADK 형식)
        content = types.Content(
            role='user',
            parts=[types.Part(text=query)]
        )

        # Runner로 실행 - 자동으로 sub_agents에게 delegation!
        responses = []
        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        responses.append(part.text)

        response = "".join(responses)

        logger.info(f"[Orchestrator] Response generated ({len(response)} chars)")

        return response


# Global orchestrator instance
_orchestrator = None


def get_orchestrator() -> LawSearchOrchestrator:
    """Global orchestrator 인스턴스 반환 (Singleton)"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = LawSearchOrchestrator()
    return _orchestrator


async def main():
    """Test orchestrator"""
    print("\n" + "="*70)
    print("Testing Law Search Orchestrator")
    print("="*70 + "\n")

    orchestrator = get_orchestrator()

    test_query = "용도지역이란 무엇인가요?"
    print(f"Query: {test_query}\n")

    response = await orchestrator.search(test_query)
    print(f"\nResponse:\n{response}")

    print("\n" + "="*70)
    print("✓ Orchestrator test complete")
    print("="*70)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
