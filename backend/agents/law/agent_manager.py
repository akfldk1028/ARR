"""
Self-Organizing Agent Manager

자가 조직화 에이전트 관리자:
- 새 PDF 자동 처리 (파싱 → 임베딩 → 도메인 할당)
- 에이전트 자동 생성 (새 도메인 발견 시)
- 에이전트 분할/병합 (크기 최적화)
- A2A 네트워크 자동 구성
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
from uuid import uuid4
import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

from django.conf import settings
from graph_db.services import Neo4jService
from law.core.law_parser_improved import ImprovedKoreanLawParser
from law.core.pdf_extractor import extract_text_from_pdf_simple

logger = logging.getLogger(__name__)


class DomainInfo:
    """도메인 정보 데이터 클래스"""

    def __init__(self, domain_id: str, domain_name: str, agent_slug: str):
        self.domain_id = domain_id
        self.domain_name = domain_name
        self.agent_slug = agent_slug
        self.node_ids: Set[str] = set()
        self.centroid: Optional[np.ndarray] = None
        self.neighbor_domains: Set[str] = set()  # A2A 네트워크
        self.created_at = datetime.now()
        self.last_updated = datetime.now()

        # ✅ 핵심: DomainAgent 인스턴스 보유
        self.agent_instance = None  # 나중에 생성

    def add_node(self, node_id: str):
        """노드 추가"""
        self.node_ids.add(node_id)
        self.last_updated = datetime.now()

    def remove_node(self, node_id: str):
        """노드 제거"""
        self.node_ids.discard(node_id)
        self.last_updated = datetime.now()

    def size(self) -> int:
        """도메인 크기 (노드 개수)"""
        return len(self.node_ids)

    def update_centroid(self, embeddings: Dict[str, np.ndarray]):
        """센트로이드 업데이트"""
        if not self.node_ids:
            self.centroid = None
            return

        vectors = [embeddings[nid] for nid in self.node_ids if nid in embeddings]
        if vectors:
            self.centroid = np.mean(vectors, axis=0)

    def to_dict(self) -> Dict:
        """딕셔너리 변환"""
        return {
            'domain_id': self.domain_id,
            'domain_name': self.domain_name,
            'agent_slug': self.agent_slug,
            'node_count': self.size(),
            'neighbor_count': len(self.neighbor_domains),
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat()
        }


class AgentManager:
    """
    자가 조직화 에이전트 관리자

    핵심 기능:
    1. process_new_pdf(): 새 PDF 자동 처리
    2. _assign_to_agents(): 자동 에이전트 할당
    3. _create_domain_agent_instance(): DomainAgent 인스턴스 동적 생성 ← 핵심!
    4. _split_agent(): 에이전트 분할 (크기 > 300)
    5. _merge_agents(): 에이전트 병합 (크기 < 50)
    6. _optimize_network(): A2A 네트워크 최적화
    """

    # 임계값 설정
    MIN_AGENT_SIZE = 50      # 최소 에이전트 크기 (이하이면 병합)
    MAX_AGENT_SIZE = 500     # 최대 에이전트 크기 (초과하면 분할)
    DOMAIN_SIMILARITY_THRESHOLD = 0.70  # 도메인 유사도 임계값 (낮춤: 0.85 → 0.70)
    NEIGHBOR_THRESHOLD = 10  # A2A 이웃 최소 cross_law 개수
    OPTIMAL_CLUSTER_RANGE = (5, 15)  # K-means 최적 클러스터 수 범위

    def __init__(self, neo4j_service: Optional[Neo4jService] = None):
        self.neo4j = neo4j_service or Neo4jService()
        self.neo4j.connect()

        # 도메인 관리
        self.domains: Dict[str, DomainInfo] = {}  # domain_id -> DomainInfo
        self.node_to_domain: Dict[str, str] = {}  # node_id -> domain_id
        self.embeddings_cache: Dict[str, np.ndarray] = {}  # node_id -> embedding

        # LLM for domain naming (OpenAI)
        from openai import OpenAI
        self.llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # ✅ Neo4j에서 기존 도메인 로드 (서버 재시작 시 복구)
        loaded_domains = self._load_domains_from_neo4j()
        if loaded_domains:
            self.domains = loaded_domains
            # node_to_domain 재구성
            for domain_id, domain in loaded_domains.items():
                for node_id in domain.node_ids:
                    self.node_to_domain[node_id] = domain_id
            logger.info(f"Loaded {len(loaded_domains)} domains from Neo4j")

            # ✅ 도메인에 속한 모든 노드의 임베딩 로드 (CRITICAL: 분할/병합에 필수!)
            all_node_ids = set()
            for domain in loaded_domains.values():
                all_node_ids.update(domain.node_ids)
            self.embeddings_cache = self._load_embeddings_from_neo4j(all_node_ids)
        else:
            # 도메인이 없으면 기존 HANG 노드로부터 자동 초기화
            hang_count = self._count_hangs_in_neo4j()
            if hang_count > 0:
                logger.info(f"No domains found, auto-initializing from {hang_count} HANG nodes...")
                self._initialize_from_existing_hangs(n_clusters=5)
            else:
                logger.info("No domains and no HANG nodes found")

        logger.info("AgentManager initialized")

    def process_new_pdf(self, pdf_path: str) -> Dict:
        """
        새 PDF 자동 처리 (핵심 메서드)

        워크플로우:
        1. PDF 텍스트 추출
        2. 법률 파싱 (HANG 단위)
        3. Neo4j 저장
        4. 임베딩 생성
        5. 자동 도메인 할당 ← 핵심!
        6. 네트워크 최적화

        Args:
            pdf_path: PDF 파일 경로

        Returns:
            처리 결과 딕셔너리
        """
        logger.info(f"Processing new PDF: {pdf_path}")
        start_time = datetime.now()

        # [1] PDF 텍스트 추출
        text = extract_text_from_pdf_simple(pdf_path)
        if not text:
            raise ValueError(f"Could not extract text from {pdf_path}")

        # [2] 법률 파싱
        law_name = self._extract_law_name(pdf_path)
        parser = ImprovedKoreanLawParser(law_name=law_name)
        units = parser.parse(text)

        # HANG 단위만 추출
        hang_units = [u for u in units if u.unit_type.value == "항"]
        logger.info(f"Parsed {len(hang_units)} HANG units")

        # [3] Neo4j 저장
        hang_ids = self._save_to_neo4j(hang_units)
        logger.info(f"Saved {len(hang_ids)} HANG nodes to Neo4j")

        # [4] 임베딩 생성
        embeddings = self._generate_embeddings(hang_ids)
        self.embeddings_cache.update(embeddings)
        logger.info(f"Generated embeddings for {len(embeddings)} nodes")

        # [5] 자동 도메인 할당 (핵심!)
        assignments = self._assign_to_agents(hang_ids, embeddings)
        logger.info(f"Assigned nodes to {len(set(assignments.values()))} domains")

        # [6] 네트워크 최적화
        optimizations = self._optimize_network()

        # 결과 반환
        duration = (datetime.now() - start_time).total_seconds()
        result = {
            'pdf_path': pdf_path,
            'law_name': law_name,
            'hang_count': len(hang_ids),
            'domains_touched': len(set(assignments.values())),
            'optimizations': optimizations,
            'duration_seconds': duration,
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"PDF processing completed in {duration:.2f}s")
        return result

    def _assign_to_agents(self, hang_ids: List[str], embeddings: Dict[str, np.ndarray]) -> Dict[str, str]:
        """
        자동 에이전트 할당 (핵심 로직!)

        알고리즘:
        - 처음 호출 시 (도메인 비어있음): K-means 클러스터링으로 초기 도메인 생성
        - 이후: 각 HANG을 기존 도메인과 비교하여 할당

        Args:
            hang_ids: HANG 노드 ID 리스트
            embeddings: 임베딩 딕셔너리

        Returns:
            node_id -> domain_id 매핑
        """
        # 처음 호출 시 K-means 클러스터링
        if not self.domains and len(hang_ids) > 100:
            logger.info(f"First-time clustering: using K-means on {len(hang_ids)} nodes")
            return self._kmeans_initial_clustering(hang_ids, embeddings)

        # 이후: 기존 방식 (순차 할당)
        assignments = {}

        for hang_id in hang_ids:
            embedding = embeddings.get(hang_id)
            if embedding is None:
                logger.warning(f"No embedding for {hang_id}, skipping")
                continue

            # 기존 도메인과 유사도 계산
            best_domain, similarity = self._find_best_domain(embedding)

            if best_domain and similarity >= self.DOMAIN_SIMILARITY_THRESHOLD:
                # 기존 도메인에 추가
                best_domain.add_node(hang_id)
                self.node_to_domain[hang_id] = best_domain.domain_id
                assignments[hang_id] = best_domain.domain_id

                logger.debug(f"Added {hang_id} to existing domain {best_domain.domain_name} (sim={similarity:.3f})")

                # 크기 체크 및 분할
                if best_domain.size() > self.MAX_AGENT_SIZE:
                    self._split_agent(best_domain)

            else:
                # 새 도메인 생성
                new_domain = self._create_new_domain([hang_id], [embedding])
                assignments[hang_id] = new_domain.domain_id

                sim_str = f"{similarity:.3f}" if similarity else "0.0"
                logger.info(f"Created new domain '{new_domain.domain_name}' for {hang_id} (max_sim={sim_str})")

        return assignments

    def _find_best_domain(self, embedding: np.ndarray) -> Tuple[Optional[DomainInfo], float]:
        """
        임베딩과 가장 유사한 도메인 찾기

        Args:
            embedding: 노드 임베딩 벡터

        Returns:
            (최적 도메인, 유사도) 튜플
        """
        if not self.domains:
            return None, 0.0

        best_domain = None
        best_similarity = 0.0

        for domain in self.domains.values():
            if domain.centroid is None:
                domain.update_centroid(self.embeddings_cache)

            if domain.centroid is not None:
                # 코사인 유사도 계산
                similarity = cosine_similarity(
                    embedding.reshape(1, -1),
                    domain.centroid.reshape(1, -1)
                )[0][0]

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_domain = domain

        return best_domain, best_similarity

    def _kmeans_initial_clustering(self, hang_ids: List[str], embeddings: Dict[str, np.ndarray]) -> Dict[str, str]:
        """
        K-means를 사용한 초기 클러스터링 (Best Practice!)

        알고리즘:
        1. Silhouette score로 최적 k 찾기 (5~15 범위)
        2. K-means 클러스터링 실행
        3. 각 클러스터에 대해 도메인 생성

        Args:
            hang_ids: HANG 노드 ID 리스트
            embeddings: 임베딩 딕셔너리

        Returns:
            node_id -> domain_id 매핑
        """
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        logger.info(f"Starting K-means clustering on {len(hang_ids)} nodes")

        # 임베딩 행렬 생성
        embedding_matrix = np.array([embeddings[hid] for hid in hang_ids if hid in embeddings])
        valid_hang_ids = [hid for hid in hang_ids if hid in embeddings]

        if len(embedding_matrix) < 10:
            logger.warning(f"Too few nodes ({len(embedding_matrix)}) for K-means, using single domain")
            return self._create_single_domain(valid_hang_ids, embedding_matrix)

        # 최적 k 찾기 (Silhouette score)
        best_k = 5
        best_score = -1.0
        min_k, max_k = self.OPTIMAL_CLUSTER_RANGE

        logger.info(f"Finding optimal k in range {min_k}~{max_k}")
        for k in range(min_k, min(max_k + 1, len(embedding_matrix) // 50)):  # 클러스터당 최소 50개
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embedding_matrix)
            score = silhouette_score(embedding_matrix, labels, metric='cosine')
            logger.info(f"  k={k}: silhouette_score={score:.3f}")

            if score > best_score:
                best_score = score
                best_k = k

        logger.info(f"Optimal k={best_k} (score={best_score:.3f})")

        # 최적 k로 클러스터링
        kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embedding_matrix)

        # 각 클러스터에 대해 도메인 생성
        assignments = {}
        for cluster_id in range(best_k):
            cluster_mask = cluster_labels == cluster_id
            cluster_hang_ids = [valid_hang_ids[i] for i in range(len(valid_hang_ids)) if cluster_mask[i]]
            cluster_embeddings = [embedding_matrix[i] for i in range(len(embedding_matrix)) if cluster_mask[i]]

            if not cluster_hang_ids:
                continue

            # 도메인 생성
            domain = self._create_new_domain(cluster_hang_ids, cluster_embeddings)
            logger.info(f"Created cluster {cluster_id+1}/{best_k}: {domain.domain_name} ({len(cluster_hang_ids)} nodes)")

            for hang_id in cluster_hang_ids:
                assignments[hang_id] = domain.domain_id

        logger.info(f"K-means clustering complete: {best_k} domains, {len(assignments)} nodes assigned")
        return assignments

    def _create_single_domain(self, hang_ids: List[str], embedding_matrix: np.ndarray) -> Dict[str, str]:
        """단일 도메인 생성 (노드 수가 적을 때)"""
        domain = self._create_new_domain(hang_ids, list(embedding_matrix))
        return {hid: domain.domain_id for hid in hang_ids}

    def _create_new_domain(self, hang_ids: List[str], embeddings: List[np.ndarray]) -> DomainInfo:
        """
        새 도메인 생성 (LLM으로 이름 자동 생성 + DomainAgent 인스턴스 생성)

        ✅ 핵심: 파일을 생성하는 게 아니라 DomainAgent 인스턴스를 메모리에 생성!

        Args:
            hang_ids: 초기 노드 ID 리스트
            embeddings: 임베딩 리스트

        Returns:
            생성된 DomainInfo
        """
        domain_id = f"domain_{uuid4().hex[:8]}"

        # LLM으로 도메인 이름 생성
        domain_name = self._generate_domain_name(hang_ids)

        # 에이전트 슬러그 생성
        agent_slug = f"law_{domain_name.replace(' ', '_').lower()}"

        # DomainInfo 생성
        domain = DomainInfo(domain_id, domain_name, agent_slug)
        for hang_id in hang_ids:
            domain.add_node(hang_id)
            self.node_to_domain[hang_id] = domain_id

        # 센트로이드 계산
        if embeddings:
            domain.centroid = np.mean(embeddings, axis=0)

        # ✅ DomainAgent 인스턴스 생성 (동적!)
        domain.agent_instance = self._create_domain_agent_instance(domain)

        # 등록
        self.domains[domain_id] = domain

        # ✅ Neo4j 동기화
        self._sync_domain_to_neo4j(domain)
        embeddings_dict = {hang_id: emb for hang_id, emb in zip(hang_ids, embeddings)}
        self._sync_domain_assignments_neo4j(domain_id, hang_ids, embeddings_dict)

        logger.info(f"Created domain: {domain_name} (ID: {domain_id}, Agent: {agent_slug})")
        return domain

    def _create_domain_agent_instance(self, domain: DomainInfo):
        """
        DomainAgent 인스턴스 동적 생성

        ✅ 핵심: 파일 100개 생성이 아니라 인스턴스 100개 생성!

        Args:
            domain: DomainInfo

        Returns:
            DomainAgent 인스턴스
        """
        from agents.law.domain_agent import DomainAgent

        # 에이전트 설정
        agent_config = {
            'rne_threshold': 0.75,
            'ine_k': 10,
            'rate_limit_per_minute': 30,
            'max_concurrent_sessions': 5
        }

        # 도메인 정보
        domain_info = {
            'domain_id': domain.domain_id,
            'domain_name': domain.domain_name,
            'node_ids': list(domain.node_ids),
            'neighbor_agents': [
                self.domains[nid].agent_slug
                for nid in domain.neighbor_domains
                if nid in self.domains
            ]
        }

        # ✅ DomainAgent 인스턴스 생성 (동적!)
        agent_instance = DomainAgent(
            agent_slug=domain.agent_slug,
            agent_config=agent_config,
            domain_info=domain_info
        )

        logger.info(f"Created DomainAgent instance for '{domain.domain_name}' ({len(domain.node_ids)} nodes)")
        return agent_instance

    def _generate_domain_name(self, hang_ids: List[str], max_samples: int = 5) -> str:
        """
        LLM으로 도메인 이름 자동 생성

        Args:
            hang_ids: 노드 ID 리스트
            max_samples: LLM에 전달할 최대 샘플 수

        Returns:
            도메인 이름 (예: "도시계획", "건축규제")
        """
        # Neo4j에서 샘플 텍스트 조회
        sample_ids = hang_ids[:max_samples]
        sample_texts = []

        query = """
        MATCH (h:HANG)
        WHERE h.full_id IN $hang_ids
        RETURN h.full_id AS id, h.content AS content
        LIMIT $limit
        """

        results = self.neo4j.execute_query(query, {
            'hang_ids': sample_ids,
            'limit': max_samples
        })

        for record in results:
            content = record['content']
            if content:
                # 너무 긴 텍스트는 자르기 (토큰 제한)
                sample_texts.append(content[:200])

        if not sample_texts:
            return "일반법규"

        # LLM 프롬프트
        prompt = f"""다음은 한국 법률 조항들의 내용입니다. 이 조항들의 공통 주제나 도메인을 2-4 단어로 짧게 요약하세요.

조항 내용:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(sample_texts))}

공통 주제 (2-4 단어):"""

        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 법률 전문가입니다. 법률 조항들의 공통 주제를 정확하고 간결하게 파악합니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=20,
                temperature=0.3
            )

            domain_name = response.choices[0].message.content.strip()
            # 따옴표, 마침표 제거
            domain_name = domain_name.strip('"\'.,').strip()

            logger.info(f"Generated domain name: {domain_name}")
            return domain_name

        except Exception as e:
            logger.error(f"Error generating domain name: {e}")
            return f"법규_{uuid4().hex[:4]}"

    def _split_agent(self, domain: DomainInfo):
        """
        에이전트 분할 (크기 > MAX_AGENT_SIZE)

        알고리즘:
        1. 도메인의 임베딩들을 K-means로 2개 클러스터 분할
        2. 각 클러스터를 새 도메인으로 생성 (DomainAgent 인스턴스도 생성)
        3. 원래 도메인 삭제

        Args:
            domain: 분할할 도메인
        """
        logger.info(f"Splitting domain '{domain.domain_name}' (size={domain.size()})")

        # 임베딩 수집
        node_ids = list(domain.node_ids)
        embeddings = [self.embeddings_cache[nid] for nid in node_ids if nid in self.embeddings_cache]

        if len(embeddings) < 2:
            logger.warning("Not enough embeddings for splitting")
            return

        # K-means 클러스터링 (k=2)
        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        # 클러스터별로 노드 분류
        cluster_0 = [node_ids[i] for i in range(len(labels)) if labels[i] == 0]
        cluster_1 = [node_ids[i] for i in range(len(labels)) if labels[i] == 1]

        # 새 도메인 생성 (DomainAgent 인스턴스도 자동 생성)
        embeddings_0 = [embeddings[i] for i in range(len(labels)) if labels[i] == 0]
        embeddings_1 = [embeddings[i] for i in range(len(labels)) if labels[i] == 1]

        domain_0 = self._create_new_domain(cluster_0, embeddings_0)
        domain_1 = self._create_new_domain(cluster_1, embeddings_1)

        # 원래 도메인 삭제
        self._delete_domain_from_neo4j(domain.domain_id)  # ✅ Neo4j 동기화
        del self.domains[domain.domain_id]

        logger.info(f"Split complete: '{domain.domain_name}' -> '{domain_0.domain_name}' ({domain_0.size()}) + '{domain_1.domain_name}' ({domain_1.size()})")

    def _merge_agents(self, domain_a: DomainInfo, domain_b: DomainInfo):
        """
        에이전트 병합 (크기가 작은 도메인들)

        Args:
            domain_a: 첫 번째 도메인
            domain_b: 두 번째 도메인
        """
        logger.info(f"Merging domains '{domain_a.domain_name}' ({domain_a.size()}) + '{domain_b.domain_name}' ({domain_b.size()})")

        # 모든 노드를 domain_a로 이동
        for node_id in domain_b.node_ids:
            domain_a.add_node(node_id)
            self.node_to_domain[node_id] = domain_a.domain_id

        # 센트로이드 재계산
        domain_a.update_centroid(self.embeddings_cache)

        # domain_a의 DomainAgent 인스턴스 업데이트
        if domain_a.agent_instance:
            domain_a.agent_instance.node_ids = domain_a.node_ids

        # ✅ Neo4j 동기화
        # 1. domain_b 삭제 (DETACH DELETE로 관계도 삭제됨)
        self._delete_domain_from_neo4j(domain_b.domain_id)

        # 2. domain_a 업데이트 (센트로이드, node_count 변경됨)
        self._sync_domain_to_neo4j(domain_a)

        # 3. domain_b의 노드들을 domain_a에 재할당
        domain_b_nodes = list(domain_b.node_ids)
        self._sync_domain_assignments_neo4j(domain_a.domain_id, domain_b_nodes, self.embeddings_cache)

        # domain_b 삭제
        del self.domains[domain_b.domain_id]

        logger.info(f"Merge complete: new size={domain_a.size()}")

    def rebalance_all_domains(self):
        """
        전체 도메인 자동 재구성 (AI 판단 기반)

        알고리즘:
        1. 크기 > 500인 도메인 자동 분할
        2. 크기 < 50인 도메인 자동 병합
        3. Neo4j 동기화

        Returns:
            재구성 결과 딕셔너리
        """
        logger.info("=" * 60)
        logger.info("Starting automatic domain rebalancing...")
        logger.info("=" * 60)

        results = {
            'domains_before': len(self.domains),
            'domains_split': 0,
            'domains_merged': 0,
            'domains_after': 0,
            'actions': []
        }

        # [1] 분할 대상 찾기 (size > MAX_AGENT_SIZE)
        domains_to_split = []
        for domain in self.domains.values():
            if domain.size() > self.MAX_AGENT_SIZE:
                domains_to_split.append(domain)
                logger.info(f"Found oversized domain: {domain.domain_name} ({domain.size()} nodes)")

        # [2] 분할 실행
        for domain in domains_to_split:
            logger.info(f"Splitting domain: {domain.domain_name} ({domain.size()} nodes)...")
            original_id = domain.domain_id
            self._split_agent(domain)
            results['domains_split'] += 1
            results['actions'].append({
                'type': 'split',
                'original': domain.domain_name,
                'size': domain.size()
            })

        # [3] 병합 대상 찾기 (size < MIN_AGENT_SIZE)
        while True:
            small_domains = [d for d in self.domains.values() if d.size() < self.MIN_AGENT_SIZE]

            if not small_domains:
                break  # 더 이상 병합할 도메인 없음

            # 가장 작은 도메인 선택
            smallest_domain = min(small_domains, key=lambda d: d.size())

            # 병합 대상 찾기 (유사도 기반)
            merge_target = self._find_merge_candidate(smallest_domain)

            if merge_target is None:
                logger.warning(f"No merge candidate for {smallest_domain.domain_name}, skipping")
                break

            logger.info(f"Merging {smallest_domain.domain_name} ({smallest_domain.size()}) → {merge_target.domain_name} ({merge_target.size()})...")
            self._merge_agents(merge_target, smallest_domain)
            results['domains_merged'] += 1
            results['actions'].append({
                'type': 'merge',
                'source': smallest_domain.domain_name,
                'target': merge_target.domain_name,
                'size': smallest_domain.size()
            })

        results['domains_after'] = len(self.domains)

        logger.info("=" * 60)
        logger.info(f"Rebalancing complete!")
        logger.info(f"  Domains before: {results['domains_before']}")
        logger.info(f"  Domains split: {results['domains_split']}")
        logger.info(f"  Domains merged: {results['domains_merged']}")
        logger.info(f"  Domains after: {results['domains_after']}")
        logger.info("=" * 60)

        return results

    def _find_merge_candidate(self, small_domain: DomainInfo) -> Optional[DomainInfo]:
        """
        병합 대상 찾기 (AI 판단 기반)

        알고리즘:
        1. 다른 도메인들과 센트로이드 유사도 계산
        2. 가장 유사하고, 병합 후 크기가 MAX_AGENT_SIZE 이하인 도메인 선택

        Args:
            small_domain: 병합할 작은 도메인

        Returns:
            병합 대상 도메인 (없으면 None)
        """
        if small_domain.centroid is None:
            small_domain.update_centroid(self.embeddings_cache)

        if small_domain.centroid is None:
            return None

        best_candidate = None
        best_similarity = -1.0

        for domain in self.domains.values():
            if domain.domain_id == small_domain.domain_id:
                continue

            # 병합 후 크기 체크
            merged_size = domain.size() + small_domain.size()
            if merged_size > self.MAX_AGENT_SIZE:
                continue  # 너무 커짐

            # 센트로이드 유사도 계산
            if domain.centroid is None:
                domain.update_centroid(self.embeddings_cache)

            if domain.centroid is not None:
                similarity = cosine_similarity(
                    small_domain.centroid.reshape(1, -1),
                    domain.centroid.reshape(1, -1)
                )[0][0]

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_candidate = domain

        if best_candidate:
            logger.info(f"Merge candidate found: {best_candidate.domain_name} (similarity={best_similarity:.3f})")

        return best_candidate

    def _optimize_network(self) -> Dict:
        """
        네트워크 최적화 (분할/병합 + A2A 이웃 재구성)

        Returns:
            최적화 통계
        """
        logger.info("Starting network optimization")

        splits = 0
        merges = 0

        # [1] 크기 기반 분할/병합
        domains_list = list(self.domains.values())

        # 분할 (크기 > MAX)
        for domain in domains_list:
            if domain.domain_id not in self.domains:
                continue  # 이미 삭제됨
            if domain.size() > self.MAX_AGENT_SIZE:
                self._split_agent(domain)
                splits += 1

        # 병합 (크기 < MIN)
        small_domains = [d for d in self.domains.values() if d.size() < self.MIN_AGENT_SIZE]

        while len(small_domains) >= 2:
            # 가장 유사한 두 도메인 찾기
            best_pair = None
            best_similarity = -1

            for i, domain_a in enumerate(small_domains):
                for domain_b in small_domains[i+1:]:
                    if domain_a.centroid is None or domain_b.centroid is None:
                        continue

                    similarity = cosine_similarity(
                        domain_a.centroid.reshape(1, -1),
                        domain_b.centroid.reshape(1, -1)
                    )[0][0]

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_pair = (domain_a, domain_b)

            if best_pair:
                self._merge_agents(best_pair[0], best_pair[1])
                merges += 1
                small_domains = [d for d in self.domains.values() if d.size() < self.MIN_AGENT_SIZE]
            else:
                break

        # [2] A2A 이웃 네트워크 재구성
        neighbors_updated = self._rebuild_neighbor_network()

        result = {
            'splits': splits,
            'merges': merges,
            'neighbors_updated': neighbors_updated,
            'total_domains': len(self.domains)
        }

        logger.info(f"Optimization complete: splits={splits}, merges={merges}, neighbors={neighbors_updated}")
        return result

    def _rebuild_neighbor_network(self) -> int:
        """
        A2A 이웃 네트워크 재구성

        알고리즘:
        1. 각 도메인 쌍에 대해 cross_law 관계 개수 계산
        2. 개수 >= NEIGHBOR_THRESHOLD이면 이웃으로 연결
        3. 각 DomainAgent 인스턴스의 neighbor_agents 업데이트

        Returns:
            업데이트된 이웃 관계 개수
        """
        # 모든 이웃 관계 초기화
        for domain in self.domains.values():
            domain.neighbor_domains.clear()

        updated_count = 0

        # Neo4j에서 cross_law 관계 계산
        query = """
        MATCH (h1:HANG)<-[:CONTAINS*]-(law1:LAW)
              -[:IMPLEMENTS*]->(law2:LAW)
              -[:CONTAINS*]->(h2:HANG)
        WHERE h1.full_id IN $domain_a_nodes
          AND h2.full_id IN $domain_b_nodes
        RETURN count(*) AS cross_law_count
        """

        domain_list = list(self.domains.values())

        for i, domain_a in enumerate(domain_list):
            for domain_b in domain_list[i+1:]:
                result = self.neo4j.execute_query(query, {
                    'domain_a_nodes': list(domain_a.node_ids),
                    'domain_b_nodes': list(domain_b.node_ids)
                })

                count = result[0]['cross_law_count'] if result else 0

                if count >= self.NEIGHBOR_THRESHOLD:
                    domain_a.neighbor_domains.add(domain_b.domain_id)
                    domain_b.neighbor_domains.add(domain_a.domain_id)

                    # ✅ DomainAgent 인스턴스 업데이트
                    if domain_a.agent_instance:
                        domain_a.agent_instance.neighbor_agents.append(domain_b.agent_slug)
                    if domain_b.agent_instance:
                        domain_b.agent_instance.neighbor_agents.append(domain_a.agent_slug)

                    updated_count += 1

        logger.info(f"Rebuilt neighbor network: {updated_count} connections")
        return updated_count

    def _extract_law_name(self, pdf_path: str) -> str:
        """PDF 파일명에서 법률명 추출"""
        import os
        filename = os.path.basename(pdf_path)
        # 확장자 제거
        name = os.path.splitext(filename)[0]
        # 숫자 및 특수문자 제거
        import re
        name = re.sub(r'^\d+_', '', name)  # 앞의 번호 제거
        name = re.sub(r'\([^)]+\)$', '', name)  # 끝의 괄호 내용 제거
        return name.strip()

    def _save_to_neo4j(self, hang_units: List) -> List[str]:
        """HANG 단위를 Neo4j에 저장"""
        hang_ids = []

        for unit in hang_units:
            hang_id = f"hang_{uuid4().hex[:12]}"

            query = """
            CREATE (h:HANG {
                hang_id: $hang_id,
                unit_number: $unit_number,
                title: $title,
                content: $content,
                unit_path: $unit_path,
                full_id: $full_id,
                created_at: $created_at
            })
            RETURN h.hang_id AS hang_id
            """

            self.neo4j.execute_query(query, {
                'hang_id': hang_id,
                'unit_number': unit.unit_number,
                'title': unit.title or "",
                'content': unit.content,
                'unit_path': unit.unit_path,
                'full_id': unit.full_id,
                'created_at': datetime.now().isoformat()
            })

            hang_ids.append(hang_id)

        return hang_ids

    def _generate_embeddings(self, hang_ids: List[str]) -> Dict[str, np.ndarray]:
        """HANG 노드의 임베딩 생성"""
        # Neo4j에서 텍스트 조회
        query = """
        MATCH (h:HANG)
        WHERE h.full_id IN $hang_ids
        RETURN h.full_id AS hang_id, h.content AS content
        """

        results = self.neo4j.execute_query(query, {'hang_ids': hang_ids})

        texts = []
        ids = []
        for record in results:
            ids.append(record['hang_id'])
            texts.append(record['content'] or "")

        # SentenceTransformer로 임베딩 생성
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('snunlp/KR-SBERT-V40K-klueNLI-augSTS')
        embeddings = model.encode(texts, show_progress_bar=False)

        # Neo4j에 저장
        for hang_id, embedding in zip(ids, embeddings):
            update_query = """
            MATCH (h:HANG {full_id: $hang_id})
            SET h.embedding = $embedding
            """
            self.neo4j.execute_query(update_query, {
                'hang_id': hang_id,
                'embedding': embedding.tolist()
            })

        return {hang_id: emb for hang_id, emb in zip(ids, embeddings)}

    def get_statistics(self) -> Dict:
        """에이전트 관리 통계"""
        return {
            'total_domains': len(self.domains),
            'total_nodes': len(self.node_to_domain),
            'domains': [d.to_dict() for d in self.domains.values()],
            'average_domain_size': np.mean([d.size() for d in self.domains.values()]) if self.domains else 0,
            'min_domain_size': min([d.size() for d in self.domains.values()]) if self.domains else 0,
            'max_domain_size': max([d.size() for d in self.domains.values()]) if self.domains else 0
        }

    def get_agent_instance(self, domain_id: str):
        """도메인 ID로 DomainAgent 인스턴스 조회"""
        domain = self.domains.get(domain_id)
        return domain.agent_instance if domain else None

    # ============== Neo4j 동기화 메서드 ==============

    def _sync_domain_to_neo4j(self, domain_info: DomainInfo):
        """
        Domain 노드를 Neo4j에 생성/업데이트

        메모리 → Neo4j 동기화 (Write-Through)

        Args:
            domain_info: 도메인 정보
        """
        try:
            centroid_list = domain_info.centroid.tolist() if domain_info.centroid is not None else []

            query = """
            MERGE (d:Domain {domain_id: $domain_id})
            SET d.domain_name = $domain_name,
                d.agent_slug = $agent_slug,
                d.node_count = $node_count,
                d.centroid_embedding = $centroid_embedding,
                d.created_at = $created_at,
                d.updated_at = $updated_at
            RETURN d.domain_id AS domain_id
            """

            self.neo4j.execute_query(query, {
                'domain_id': domain_info.domain_id,
                'domain_name': domain_info.domain_name,
                'agent_slug': domain_info.agent_slug,
                'node_count': domain_info.size(),
                'centroid_embedding': centroid_list,
                'created_at': domain_info.created_at.isoformat(),
                'updated_at': domain_info.last_updated.isoformat()
            })

            logger.info(f"✓ Domain synced to Neo4j: {domain_info.domain_name} ({domain_info.size()} nodes)")

        except Exception as e:
            logger.warning(f"Neo4j domain sync failed (continuing with memory): {e}")

    def _sync_domain_assignments_neo4j(self, domain_id: str, hang_ids: List[str], embeddings: Dict[str, np.ndarray]):
        """
        HANG 노드들을 Domain에 할당 (BELONGS_TO_DOMAIN 관계 생성)

        배치 처리로 성능 최적화 (1000개씩)

        Args:
            domain_id: 도메인 ID
            hang_ids: HANG 노드 ID 목록
            embeddings: 임베딩 딕셔너리 (유사도 계산용)
        """
        try:
            domain_info = self.domains.get(domain_id)
            if not domain_info or not domain_info.centroid is not None:
                return

            # 배치 처리 (1000개씩)
            batch_size = 1000
            for i in range(0, len(hang_ids), batch_size):
                batch = hang_ids[i:i+batch_size]

                # 유사도 계산
                similarities = []
                for hang_id in batch:
                    if hang_id in embeddings:
                        sim = cosine_similarity(
                            [domain_info.centroid],
                            [embeddings[hang_id]]
                        )[0][0]
                        similarities.append(float(sim))
                    else:
                        similarities.append(0.0)

                # UNWIND로 배치 생성
                query = """
                UNWIND $items AS item
                MATCH (h:HANG {full_id: item.hang_id})
                MATCH (d:Domain {domain_id: $domain_id})
                MERGE (h)-[r:BELONGS_TO_DOMAIN]->(d)
                SET r.similarity = item.similarity,
                    r.assigned_at = datetime()
                """

                items = [
                    {'hang_id': hang_id, 'similarity': sim}
                    for hang_id, sim in zip(batch, similarities)
                ]

                self.neo4j.execute_query(query, {
                    'domain_id': domain_id,
                    'items': items
                })

            logger.info(f"✓ {len(hang_ids)} HANG nodes assigned to {domain_info.domain_name}")

        except Exception as e:
            logger.warning(f"Neo4j assignment sync failed (continuing with memory): {e}")

    def _delete_domain_from_neo4j(self, domain_id: str):
        """
        Domain 노드 삭제 (BELONGS_TO_DOMAIN 관계도 자동 삭제)

        Args:
            domain_id: 삭제할 도메인 ID
        """
        try:
            query = """
            MATCH (d:Domain {domain_id: $domain_id})
            DETACH DELETE d
            """

            self.neo4j.execute_query(query, {'domain_id': domain_id})
            logger.info(f"✓ Domain deleted from Neo4j: {domain_id}")

        except Exception as e:
            logger.warning(f"Neo4j domain deletion failed: {e}")

    def _load_domains_from_neo4j(self) -> Dict[str, DomainInfo]:
        """
        서버 시작 시 Neo4j에서 도메인 로드

        Returns:
            domain_id -> DomainInfo 딕셔너리
        """
        try:
            # Domain 노드 조회
            query = """
            MATCH (d:Domain)
            OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
            RETURN d.domain_id AS domain_id,
                   d.domain_name AS domain_name,
                   d.agent_slug AS agent_slug,
                   d.created_at AS created_at,
                   d.updated_at AS updated_at,
                   d.centroid_embedding AS centroid_embedding,
                   collect(h.full_id) AS hang_ids
            """

            results = self.neo4j.execute_query(query, {})

            if not results:
                logger.info("No domains found in Neo4j")
                return {}

            domains = {}

            for record in results:
                domain_id = record['domain_id']
                domain_name = record['domain_name']
                agent_slug = record['agent_slug']

                # DomainInfo 재구성
                domain_info = DomainInfo(domain_id, domain_name, agent_slug)

                # created_at/updated_at 복원
                if record.get('created_at'):
                    domain_info.created_at = datetime.fromisoformat(record['created_at'])
                if record.get('updated_at'):
                    domain_info.last_updated = datetime.fromisoformat(record['updated_at'])

                # centroid 복원
                if record.get('centroid_embedding'):
                    domain_info.centroid = np.array(record['centroid_embedding'])

                # node_ids 복원
                hang_ids = [hid for hid in record.get('hang_ids', []) if hid]
                domain_info.node_ids = set(hang_ids)

                # ✅ DomainAgent 인스턴스 생성 (필수!)
                domain_info.agent_instance = self._create_domain_agent_instance(domain_info)

                domains[domain_id] = domain_info

                logger.info(f"Loaded domain from Neo4j: {domain_name} ({len(hang_ids)} nodes)")

            logger.info(f"✓ Loaded {len(domains)} domains from Neo4j")
            return domains

        except Exception as e:
            logger.warning(f"Failed to load domains from Neo4j: {e}")
            return {}

    def _count_hangs_in_neo4j(self) -> int:
        """
        Neo4j에서 임베딩이 있는 HANG 노드 개수 확인

        Returns:
            HANG 노드 개수
        """
        try:
            query = """
            MATCH (h:HANG)
            WHERE h.embedding IS NOT NULL
            RETURN count(h) AS count
            """

            result = self.neo4j.execute_query(query, {})
            return result[0]['count'] if result else 0

        except Exception as e:
            logger.warning(f"Failed to count HANG nodes: {e}")
            return 0

    def _load_embeddings_from_neo4j(self, node_ids: set) -> Dict[str, np.ndarray]:
        """
        Neo4j에서 지정된 HANG 노드들의 임베딩 로드

        Args:
            node_ids: 로드할 HANG 노드 ID 집합

        Returns:
            node_id -> embedding 딕셔너리
        """
        if not node_ids:
            return {}

        try:
            logger.info(f"Loading embeddings for {len(node_ids)} nodes from Neo4j...")

            query = """
            MATCH (h:HANG)
            WHERE h.full_id IN $node_ids
              AND h.embedding IS NOT NULL
            RETURN h.full_id AS node_id, h.embedding AS embedding
            """

            results = self.neo4j.execute_query(query, {'node_ids': list(node_ids)})

            embeddings = {}
            for record in results:
                node_id = record['node_id']
                embedding_list = record['embedding']
                if embedding_list:
                    embeddings[node_id] = np.array(embedding_list)

            logger.info(f"✓ Loaded {len(embeddings)} embeddings from Neo4j")
            return embeddings

        except Exception as e:
            logger.warning(f"Failed to load embeddings from Neo4j: {e}")
            return {}

    def _initialize_from_existing_hangs(self, n_clusters: int = 5):
        """
        기존 HANG 노드들로부터 자동 도메인 초기화

        서버 첫 시작 시 Neo4j에 Domain이 없을 때 자동 실행됨.
        모든 HANG 노드의 임베딩을 K-means 클러스터링하여
        도메인을 생성하고 Neo4j에 동기화함.

        Args:
            n_clusters: 생성할 도메인 개수 (기본 5개)
        """
        logger.info(f"Initializing {n_clusters} domains from existing HANG nodes...")

        try:
            # [1] 모든 HANG 임베딩 로드
            query = """
            MATCH (h:HANG)
            WHERE h.embedding IS NOT NULL
            RETURN h.full_id AS hang_id, h.embedding AS embedding
            ORDER BY h.full_id
            """

            results = self.neo4j.execute_query(query, {})

            if not results:
                logger.warning("No HANG nodes with embeddings found")
                return

            hang_ids = []
            embeddings = []

            for record in results:
                hang_ids.append(record['hang_id'])
                embeddings.append(np.array(record['embedding']))

            embeddings = np.array(embeddings)
            logger.info(f"Loaded {len(hang_ids)} HANG nodes with embeddings")

            # [2] K-means 클러스터링
            logger.info(f"Clustering into {n_clusters} domains...")
            kmeans = KMeans(
                n_clusters=n_clusters,
                random_state=42,
                n_init=10,
                max_iter=300
            )
            labels = kmeans.fit_predict(embeddings)

            # 클러스터 크기 출력
            for i in range(n_clusters):
                count = np.sum(labels == i)
                logger.info(f"  Cluster {i}: {count} nodes")

            # [3] 각 클러스터를 도메인으로 생성
            for cluster_id in range(n_clusters):
                cluster_mask = labels == cluster_id
                cluster_hang_ids = [hang_ids[i] for i in range(len(hang_ids)) if cluster_mask[i]]
                cluster_embeddings = [embeddings[i] for i in range(len(embeddings)) if cluster_mask[i]]

                if len(cluster_hang_ids) == 0:
                    continue

                logger.info(f"Creating domain for cluster {cluster_id} ({len(cluster_hang_ids)} nodes)...")

                # _create_new_domain()이 자동으로:
                # 1. DomainInfo 생성
                # 2. LLM으로 도메인 이름 생성
                # 3. _sync_domain_to_neo4j() 호출
                # 4. _sync_domain_assignments_neo4j() 호출
                domain = self._create_new_domain(cluster_hang_ids, cluster_embeddings)

                logger.info(f"  Created domain: '{domain.domain_name}' ({domain.size()} nodes)")

            logger.info(f"Domain initialization complete! Created {len(self.domains)} domains")

        except Exception as e:
            logger.error(f"Failed to initialize domains from existing HANGs: {e}")
            import traceback
            traceback.print_exc()
