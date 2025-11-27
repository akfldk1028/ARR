"""
DomainAgentFactory - LangGraph 에이전트를 동적으로 생성

Factory Pattern으로 각 도메인마다 LangGraph workflow instance를 생성

**핵심 변경**: 백엔드 DomainAgent의 RNE/INE 검색 알고리즘 재사용!
"""

import sys
import os
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "shared"))
sys.path.insert(0, str(Path(__file__).parent / "agents"))

from typing import Dict, Optional
import logging

from langgraph.graph import StateGraph, START, END, MessagesState
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# Custom state for law domain agent
class LawAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    search_results: list

from domain_manager import DomainInfo
from shared.neo4j_client import get_neo4j_client
from shared.openai_client import get_openai_client
from law_search_engine import LawSearchEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LawDomainAgent:
    """
    범용 법률 도메인 에이전트

    domain_info를 파라미터로 받아서 동작하는 에이전트
    """

    def __init__(self, domain_info: DomainInfo):
        """
        Args:
            domain_info: 도메인 메타데이터
        """
        self.domain_info = domain_info
        self.neo4j_client = get_neo4j_client()
        self.openai_client = get_openai_client()

        # LawSearchEngine 초기화 (RNE/INE 알고리즘 포함)
        self.search_engine = LawSearchEngine(
            neo4j_client=self.neo4j_client,
            openai_client=self.openai_client,
            domain_id=domain_info.domain_id,
            domain_name=domain_info.domain_name,
            rne_threshold=0.65,  # RNE 유사도 임계값 (낮춤: 더 많은 결과)
            ine_k=10  # INE top-k 결과
        )

        # LLM 초기화
        self.llm = init_chat_model(
            "openai:gpt-4o",
            temperature=0.1
        )

        # LangGraph workflow 생성
        self.graph = self._build_graph()

        logger.info(f"LawDomainAgent created for '{domain_info.domain_name}'")

    def _build_graph(self) -> StateGraph:
        """
        LangGraph workflow 구축

        노드:
        1. search_domain - 도메인 내 검색
        2. generate_response - 응답 생성
        """

        def search_domain(state: LawAgentState) -> LawAgentState:
            """도메인 내 검색 노드"""
            logger.info(f"[{self.domain_info.domain_name}] Searching...")

            # 마지막 메시지 추출
            last_message = state["messages"][-1]
            query = last_message.content if hasattr(last_message, 'content') else str(last_message)

            # Orchestrator가 추가한 텍스트 제거
            import re
            # 패턴 1: "[...] called tool ..." 제거
            query = re.sub(r'\s*\[.*?\].*?called\s+tool.*$', '', query, flags=re.DOTALL)
            # 패턴 2: "..." 제거
            query = re.sub(r'\s*\.\.\.+\s*$', '', query)
            query = query.strip()

            logger.info(f"[{self.domain_info.domain_name}] Cleaned query: {query}")

            # Neo4j 검색 (간단한 버전)
            results = self._search_neo4j(query)

            logger.info(f"[{self.domain_info.domain_name}] Found {len(results)} results")

            # 상태 업데이트
            return {
                "messages": state["messages"],
                "search_results": results
            }

        def generate_response(state: LawAgentState) -> LawAgentState:
            """응답 생성 노드"""
            logger.info(f"[{self.domain_info.domain_name}] Generating response...")

            # 검색 결과 포맷팅
            search_results = state.get("search_results", [])
            logger.info(f"[{self.domain_info.domain_name}] Formatting {len(search_results)} search results")
            formatted_results = self._format_search_results(search_results)
            logger.info(f"[{self.domain_info.domain_name}] Formatted results length: {len(formatted_results)} chars")

            # 마지막 메시지
            last_message = state["messages"][-1]
            query = last_message.content if hasattr(last_message, 'content') else str(last_message)

            # System prompt
            system_prompt = f"""당신은 {self.domain_info.domain_name} 법률 전문 AI 어시스턴트입니다.

사용자의 질문에 대해 다음 검색 결과를 바탕으로 정확하고 유용한 답변을 제공하세요.

검색 결과:
{formatted_results}

답변 지침:
1. 검색된 법률 조항을 명확히 인용하세요
2. 조항의 의미를 쉽게 설명하세요
3. 관련 법조문이 여러 개인 경우 체계적으로 정리하세요
4. 검색 결과가 없는 경우, 솔직하게 밝히고 일반적인 정보를 제공하세요

사용자 질문: {query}
"""

            # LLM 호출
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ])

            logger.info(f"[{self.domain_info.domain_name}] Response generated")

            # 메시지 추가
            return {
                "messages": state["messages"] + [AIMessage(content=response.content)]
            }

        # StateGraph 구축
        workflow = StateGraph(LawAgentState)

        # 노드 추가
        workflow.add_node("search", search_domain)
        workflow.add_node("generate", generate_response)

        # 엣지 추가
        workflow.add_edge(START, "search")
        workflow.add_edge("search", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    def _search_neo4j(self, query: str) -> list:
        """
        Neo4j에서 검색 (RNE/INE 알고리즘 사용)

        LawSearchEngine을 사용하여 고급 검색 수행:
        - Hybrid Search (Exact + Vector + Relationship)
        - RNE Graph Expansion
        - Reciprocal Rank Fusion
        """
        try:
            # LawSearchEngine을 사용하여 검색
            results = self.search_engine.search(query, top_k=10)

            # 결과 포맷팅 (기존 형식 유지)
            search_results = []
            for result in results:
                search_results.append({
                    "hang_id": result["hang_id"],
                    "content": result["content"],
                    "similarity": result.get("similarity", 0.0),
                    "stage": result.get("stage", "unknown")
                })

            return search_results

        except Exception as e:
            logger.error(f"Search engine error: {e}", exc_info=True)
            return []

    def _format_search_results(self, results: list) -> str:
        """검색 결과 포맷팅"""
        if not results:
            return "검색 결과가 없습니다."

        formatted = []
        for idx, result in enumerate(results, 1):
            # 유사도와 검색 단계 정보 포함
            similarity = result.get('similarity', 0.0)
            stage = result.get('stage', 'unknown')

            formatted.append(
                f"{idx}. {result['hang_id']} (유사도: {similarity:.3f}, 단계: {stage})\n"
                f"   {result['content'][:200]}..."
            )

        return "\n\n".join(formatted)

    async def ainvoke(self, message: str) -> str:
        """
        비동기 메시지 처리

        Args:
            message: 사용자 메시지

        Returns:
            에이전트 응답
        """
        result = await self.graph.ainvoke({
            "messages": [HumanMessage(content=message)]
        })

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]
        return last_message.content if hasattr(last_message, 'content') else str(last_message)

    def invoke(self, message: str) -> str:
        """
        동기 메시지 처리

        Args:
            message: 사용자 메시지

        Returns:
            에이전트 응답
        """
        result = self.graph.invoke({
            "messages": [HumanMessage(content=message)]
        })

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]
        return last_message.content if hasattr(last_message, 'content') else str(last_message)


class DomainAgentFactory:
    """
    도메인 에이전트 팩토리

    각 도메인마다 LawDomainAgent 인스턴스를 동적으로 생성하고 캐싱
    """

    def __init__(self):
        """팩토리 초기화"""
        self._agents_cache: Dict[str, LawDomainAgent] = {}
        logger.info("DomainAgentFactory initialized")

    def create_agent(self, domain_info: DomainInfo) -> LawDomainAgent:
        """
        도메인 에이전트 생성 또는 캐시에서 반환

        Args:
            domain_info: 도메인 메타데이터

        Returns:
            LawDomainAgent 인스턴스
        """
        domain_id = domain_info.domain_id

        # 캐시 확인
        if domain_id in self._agents_cache:
            logger.info(f"Returning cached agent for '{domain_info.domain_name}'")
            return self._agents_cache[domain_id]

        # 새 에이전트 생성
        logger.info(f"Creating new agent for '{domain_info.domain_name}'")
        agent = LawDomainAgent(domain_info)

        # 캐싱
        self._agents_cache[domain_id] = agent

        return agent

    def get_agent(self, domain_id: str) -> Optional[LawDomainAgent]:
        """
        캐시에서 에이전트 가져오기

        Args:
            domain_id: 도메인 ID

        Returns:
            LawDomainAgent 또는 None
        """
        return self._agents_cache.get(domain_id)

    def clear_cache(self):
        """캐시 초기화"""
        logger.info("Clearing agent cache")
        self._agents_cache.clear()

    def get_stats(self) -> Dict:
        """팩토리 통계"""
        return {
            "total_agents": len(self._agents_cache),
            "domains": [
                {
                    "domain_id": agent.domain_info.domain_id,
                    "domain_name": agent.domain_info.domain_name
                }
                for agent in self._agents_cache.values()
            ]
        }


# 전역 팩토리 인스턴스
_factory = None

def get_agent_factory() -> DomainAgentFactory:
    """전역 DomainAgentFactory 반환"""
    global _factory
    if _factory is None:
        _factory = DomainAgentFactory()
    return _factory
