"""
DomainManager - Neo4j에서 도메인 목록을 동적으로 로드

Backend 코드 참고:
- backend/law/scripts/initialize_domains.py
- backend/graph_db/services/neo4j_service.py
"""

import sys
import os
from pathlib import Path

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent / "shared"))

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from shared.neo4j_client import get_neo4j_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DomainInfo:
    """도메인 메타데이터"""
    domain_id: str
    domain_name: str
    description: str
    node_count: int
    created_at: datetime
    updated_at: datetime

    def agent_slug(self) -> str:
        """A2A 프로토콜용 slug 생성"""
        # 예: "도시계획 및 이용" -> "urban_planning"
        slug_map = {
            "도시계획 및 이용": "urban_planning",
            "개발행위": "development_activities",
            "토지거래": "land_transactions",
            "용도지역": "land_use_zones",
            "도시개발": "urban_development"
        }
        return slug_map.get(self.domain_name, f"domain_{self.domain_id}")


class DomainManager:
    """
    도메인 관리자 - Neo4j에서 도메인 목록을 동적으로 로드

    핵심 기능:
    1. Neo4j Domain 노드 쿼리
    2. 도메인 메타데이터 캐싱
    3. 도메인 변경 감지
    """

    _instance: Optional['DomainManager'] = None

    def __init__(self):
        """싱글톤 패턴"""
        self.neo4j_client = get_neo4j_client()
        self._domains_cache: Dict[str, DomainInfo] = {}
        self._last_refresh: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5분

        logger.info("DomainManager initialized")

    @classmethod
    def get_instance(cls) -> 'DomainManager':
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_all_domains(self, force_refresh: bool = False) -> List[DomainInfo]:
        """
        모든 도메인 목록 반환

        Args:
            force_refresh: True면 캐시 무시하고 Neo4j에서 새로 로드

        Returns:
            도메인 정보 리스트
        """
        # 캐시 유효성 검사
        if not force_refresh and self._is_cache_valid():
            logger.info(f"Returning {len(self._domains_cache)} domains from cache")
            return list(self._domains_cache.values())

        # Neo4j에서 도메인 로드
        logger.info("Loading domains from Neo4j...")
        self._load_domains_from_neo4j()

        return list(self._domains_cache.values())

    def get_domain(self, domain_id: str) -> Optional[DomainInfo]:
        """
        특정 도메인 정보 반환

        Args:
            domain_id: 도메인 ID

        Returns:
            도메인 정보 또는 None
        """
        if not self._domains_cache:
            self.get_all_domains()

        return self._domains_cache.get(domain_id)

    def get_domain_by_slug(self, slug: str) -> Optional[DomainInfo]:
        """
        Slug로 도메인 찾기

        Args:
            slug: A2A agent slug (예: "urban_planning")

        Returns:
            도메인 정보 또는 None
        """
        if not self._domains_cache:
            self.get_all_domains()

        for domain in self._domains_cache.values():
            if domain.agent_slug() == slug:
                return domain

        return None

    def refresh(self) -> Dict[str, int]:
        """
        도메인 목록 강제 새로고침

        Returns:
            통계 정보 (total, added, removed)
        """
        old_domains = set(self._domains_cache.keys())

        self.get_all_domains(force_refresh=True)

        new_domains = set(self._domains_cache.keys())

        added = new_domains - old_domains
        removed = old_domains - new_domains

        stats = {
            "total": len(new_domains),
            "added": len(added),
            "removed": len(removed)
        }

        if added:
            logger.info(f"Added domains: {added}")
        if removed:
            logger.warning(f"Removed domains: {removed}")

        return stats

    def _is_cache_valid(self) -> bool:
        """캐시 유효성 검사"""
        if not self._last_refresh:
            return False

        elapsed = (datetime.now() - self._last_refresh).total_seconds()
        return elapsed < self._cache_ttl_seconds

    def _load_domains_from_neo4j(self):
        """
        Neo4j에서 도메인 로드

        쿼리:
        MATCH (d:Domain)
        OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
        WITH d, count(h) as node_count
        RETURN d.domain_id, d.domain_name, d.description,
               node_count, d.created_at, d.updated_at
        """
        query = """
        MATCH (d:Domain)
        OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
        WITH d, count(h) as actual_node_count
        RETURN
            d.domain_id as domain_id,
            d.domain_name as domain_name,
            d.description as description,
            actual_node_count as node_count,
            d.created_at as created_at,
            d.updated_at as updated_at
        ORDER BY d.domain_name
        """

        try:
            session = self.neo4j_client.get_session()
            results = session.run(query)

            new_cache = {}

            for record in results:
                domain_id = record["domain_id"]

                # datetime 변환 (Neo4j에서 string으로 저장된 경우)
                created_at = record.get("created_at")
                updated_at = record.get("updated_at")

                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                elif created_at is None:
                    created_at = datetime.now()

                if isinstance(updated_at, str):
                    updated_at = datetime.fromisoformat(updated_at)
                elif updated_at is None:
                    updated_at = datetime.now()

                domain = DomainInfo(
                    domain_id=domain_id,
                    domain_name=record["domain_name"],
                    description=record.get("description", ""),
                    node_count=record.get("node_count", 0),
                    created_at=created_at,
                    updated_at=updated_at
                )

                new_cache[domain_id] = domain

            session.close()

            self._domains_cache = new_cache
            self._last_refresh = datetime.now()

            logger.info(f"Loaded {len(new_cache)} domains from Neo4j")

        except Exception as e:
            logger.error(f"Failed to load domains from Neo4j: {e}", exc_info=True)
            # 캐시가 없으면 빈 딕셔너리 유지
            if not self._domains_cache:
                self._domains_cache = {}


# 전역 인스턴스 (선택적)
_domain_manager = None

def get_domain_manager() -> DomainManager:
    """전역 DomainManager 인스턴스 반환"""
    global _domain_manager
    if _domain_manager is None:
        _domain_manager = DomainManager.get_instance()
    return _domain_manager
