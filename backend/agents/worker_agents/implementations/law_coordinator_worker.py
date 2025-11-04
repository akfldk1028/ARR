"""
Law Coordinator Worker Agent - 한국 법률 검색 전문 에이전트

역할:
- A2A 시스템과 MAS (Multi-Agent System) 연결
- 사용자 질의를 AgentManager에게 위임
- AgentManager가 자동으로 적절한 DomainAgent에게 라우팅
- 법률이 많아질수록 (20개 → 200개) 효율성 증가

워크플로우:
User → LawCoordinatorWorker
     → AgentManager
          ├─ 도메인 자동 감지
          ├─ DomainAgent #1 (도시계획)
          ├─ DomainAgent #2 (건축규제)
          └─ DomainAgent #3 (토지이용)
"""

import os
import asyncio
import logging
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from ..base import BaseWorkerAgent
from agents.law.agent_manager import AgentManager

logger = logging.getLogger(__name__)


class LawCoordinatorWorker(BaseWorkerAgent):
    """
    법률 검색 코디네이터 Worker

    특징:
    - BaseWorkerAgent 상속 (A2A 시스템 호환)
    - AgentManager 통합 (MAS 활용)
    - 자가 조직화 도메인 관리
    - RNE/INE 알고리즘 기반 검색
    """

    def __init__(self, agent_slug: str, agent_config: Dict[str, Any]):
        super().__init__(agent_slug, agent_config)

        # AgentManager 초기화 (MAS 핵심)
        try:
            self.agent_manager = AgentManager()
            logger.info("AgentManager initialized successfully")

            # 기존 HANG 노드 로드 및 도메인 자동 생성
            self._initialize_domains()

        except Exception as e:
            logger.error(f"Failed to initialize AgentManager: {e}")
            self.agent_manager = None

        # LLM 초기화 (응답 포맷팅용)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, LLM disabled")
            self.llm = None
        else:
            django_config = agent_config.get('django', {})
            model_config = django_config.get('model_config', {})

            model_name = model_config.get('model_name', 'gpt-4o-mini') if model_config else 'gpt-4o-mini'
            temperature = model_config.get('temperature', 0.3) if model_config else 0.3

            self.llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                temperature=temperature,
                max_tokens=2048
            )
            logger.info(f"LawCoordinatorWorker initialized with model: {model_name}")

    def _initialize_domains(self):
        """
        기존 HANG 노드 로드 및 도메인 자동 생성

        순서:
        1. Neo4j에서 기존 Domain 노드 확인
        2. 이미 있으면 로드만 (재클러스터링 안 함)
        3. 없으면 K-means로 초기 클러스터링
        """
        if not self.agent_manager:
            return

        try:
            # 이미 도메인이 있으면 스킵
            if self.agent_manager.domains:
                logger.info(f"Domains already loaded: {len(self.agent_manager.domains)} domains")
                for domain_id, domain in self.agent_manager.domains.items():
                    logger.info(f"   - {domain.domain_name}: {domain.size()} nodes")
                return

            logger.info("No existing domains found, will perform K-means clustering on first query")

        except Exception as e:
            logger.error(f"Error initializing domains: {e}")
            import traceback
            traceback.print_exc()

    @property
    def agent_name(self) -> str:
        return self.config.get('name', 'Law Coordinator Agent')

    @property
    def agent_description(self) -> str:
        return self.config.get('description', '한국 법률 검색 전문 에이전트 (MAS 기반)')

    @property
    def capabilities(self) -> List[str]:
        return self.config.get('capabilities', [
            'text',
            'legal_search',
            'semantic_graph_search',
            'cross_law_reference',
            'multi_agent_coordination'
        ])

    @property
    def system_prompt(self) -> str:
        domain_summary = self._get_domain_summary()

        return self.config.get('system_prompt', f'''당신은 한국 법률 전문 AI 어시스턴트입니다.

{domain_summary}

핵심 기능:
1. **의미론적 검색**: 벡터 검색 + 그래프 확장 (RNE/INE 알고리즘)
2. **Cross-law 참조**: 법률 → 시행령 → 시행규칙 자동 탐색
3. **다중 도메인 협업**: 여러 법률 영역 통합 검색

검색 방식:
- Stage 1: Vector Search (의미론적 유사도)
- Stage 2: Graph Expansion (RNE/INE로 연관 조항 탐색)
- Stage 3: Cross-law 확장 (IMPLEMENTS 관계)

응답 형식:
1. 핵심 조항 (가장 관련도 높은 3개)
2. 연관 조항 (그래프 확장으로 발견)
3. 시행령/시행규칙 (cross_law 관계)
4. 출처 정보 (법률명, 조항 경로)

IMPORTANT:
- 정확한 법률 조항 경로 제공 (예: "국토의 계획 및 이용에 관한 법률 > 제2장 > 제12조 > 제1항")
- 유사도 점수 표시 (사용자 신뢰도 향상)
- 법률/시행령/시행규칙 구분
- 이모지 사용 금지

항상 정확하고 신뢰할 수 있는 법률 정보를 제공하세요.
''')

    def _get_domain_summary(self) -> str:
        """도메인 요약 정보 생성"""
        if not self.agent_manager or not self.agent_manager.domains:
            return "현재 등록된 법률: 로딩 중..."

        domains_info = []
        for domain in self.agent_manager.domains.values():
            domains_info.append(f"- {domain.domain_name}: {domain.size()}개 조항")

        total_nodes = sum(d.size() for d in self.agent_manager.domains.values())

        summary = [
            f"현재 {len(self.agent_manager.domains)}개 법률 도메인 관리 중:",
            *domains_info,
            f"총 {total_nodes}개 법률 조항 검색 가능"
        ]

        return "\n".join(summary)

    async def _generate_response(self, user_input: str, context_id: str, session_id: str, user_name: str) -> str:
        """
        사용자 질의 처리 (핵심 메서드)

        워크플로우:
        1. AgentManager.search() 호출
        2. 도메인 자동 라우팅
        3. DomainAgent 검색 실행
        4. 결과 통합 및 응답 생성

        Args:
            user_input: 사용자 질의
            context_id: 컨텍스트 ID
            session_id: 세션 ID
            user_name: 사용자 이름

        Returns:
            법률 검색 응답
        """
        try:
            logger.info(f"[LawCoordinator] Processing query: {user_input[:50]}...")

            # AgentManager 사용 가능 확인
            if not self.agent_manager:
                return "죄송합니다. 법률 검색 시스템이 초기화되지 않았습니다."

            # 도메인이 없는 경우
            if not self.agent_manager.domains:
                return (
                    "죄송합니다. 현재 등록된 법률 도메인이 없습니다.\n"
                    "법률 PDF를 먼저 처리해주세요."
                )

            # AgentManager를 통한 검색
            result = await self._search_through_agent_manager(user_input)

            return result

        except Exception as e:
            logger.error(f"Error in LawCoordinatorWorker._generate_response: {e}")
            import traceback
            traceback.print_exc()
            return f"죄송합니다. 법률 검색 중 오류가 발생했습니다: {str(e)}"

    async def _search_through_agent_manager(self, query: str) -> str:
        """
        AgentManager를 통한 법률 검색

        Args:
            query: 사용자 질의

        Returns:
            검색 결과 응답
        """
        # 쿼리 임베딩 생성
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
        query_embedding = model.encode(query).tolist()

        # 가장 적합한 도메인 찾기
        best_domain = self._find_best_domain(query_embedding)

        if not best_domain:
            return "죄송합니다. 관련 법률 도메인을 찾지 못했습니다."

        logger.info(f"Selected domain: {best_domain.domain_name}")

        # DomainAgent 인스턴스 가져오기
        agent_instance = best_domain.agent_instance

        if not agent_instance:
            # 인스턴스가 없으면 생성
            agent_instance = self.agent_manager._create_domain_agent_instance(best_domain)
            best_domain.agent_instance = agent_instance

        # DomainAgent 검색 실행
        try:
            # DomainAgent._search_my_domain() 호출
            results = await agent_instance._search_my_domain(query)

            # 응답 포맷팅
            response = self._format_law_response(query, results, best_domain.domain_name)

            return response

        except Exception as e:
            logger.error(f"Error searching domain {best_domain.domain_name}: {e}")
            return f"죄송합니다. {best_domain.domain_name} 도메인 검색 중 오류가 발생했습니다."

    def _find_best_domain(self, query_embedding: List[float]) -> Any:
        """
        쿼리 임베딩과 가장 유사한 도메인 찾기

        Args:
            query_embedding: 쿼리 임베딩

        Returns:
            DomainInfo 또는 None
        """
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity

        query_vec = np.array(query_embedding).reshape(1, -1)

        best_domain = None
        best_similarity = -1.0

        for domain in self.agent_manager.domains.values():
            if domain.centroid is None:
                # centroid 업데이트
                domain.update_centroid(self.agent_manager.embeddings_cache)

            if domain.centroid is not None:
                centroid_vec = domain.centroid.reshape(1, -1)
                similarity = cosine_similarity(query_vec, centroid_vec)[0][0]

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_domain = domain

        logger.info(f"Best domain: {best_domain.domain_name if best_domain else 'None'} (similarity: {best_similarity:.3f})")

        return best_domain

    def _format_law_response(self, query: str, results: List[Dict], domain_name: str) -> str:
        """
        법률 검색 결과 포맷팅

        Args:
            query: 사용자 질의
            results: 검색 결과
            domain_name: 도메인 이름

        Returns:
            포맷팅된 응답
        """
        if not results:
            return f"'{query}'에 대한 관련 법률 조항을 찾지 못했습니다."

        response_parts = [
            f"'{query}'에 대한 {domain_name} 관련 법률 정보입니다.\n"
        ]

        # 핵심 조항 (Top 3)
        response_parts.append("\n[핵심 조항]")
        for i, r in enumerate(results[:3], 1):
            response_parts.append(
                f"\n{i}. {r['unit_path']} (유사도: {r['similarity']:.2f})\n"
                f"   {r['content'][:200]}..."
            )

        # 연관 조항 (4~6위)
        if len(results) > 3:
            response_parts.append("\n\n[연관 조항]")
            for i, r in enumerate(results[3:6], 4):
                response_parts.append(
                    f"\n{i}. {r['unit_path']} (유사도: {r['similarity']:.2f})"
                )

        # Stage별 통계
        stage_counts = {}
        for r in results:
            stage = r.get('stage', 'unknown')
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        response_parts.append("\n\n[검색 통계]")
        response_parts.append(f"총 {len(results)}개 조항 발견")
        response_parts.append(f"- 벡터 검색: {stage_counts.get('vector', 0)}개")
        response_parts.append(f"- 그래프 확장: {stage_counts.get('graph_expansion', 0)}개")
        response_parts.append(f"- Cross-law: {stage_counts.get('cross_law', 0)}개")

        return ''.join(response_parts)
