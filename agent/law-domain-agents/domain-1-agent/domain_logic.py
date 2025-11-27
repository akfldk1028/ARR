"""
Domain-specific search logic for Domain 1

Integrates with Neo4j for law article search.
Will be enhanced with RNE/INE algorithms from backend.
"""

import sys
import os

# Add parent directory to path for shared imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.neo4j_client import get_neo4j_client
from shared.openai_client import get_openai_client
from config import config
import logging

logger = logging.getLogger(__name__)


class Domain1SearchLogic:
    """Search logic for Domain 1: 도시계획 및 이용"""

    def __init__(self):
        self.neo4j_client = get_neo4j_client()
        self.openai_client = get_openai_client()
        self.domain_id = config.DOMAIN_ID
        self.domain_name = config.DOMAIN_NAME

    def search_by_query(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Search for relevant law articles based on query

        This is a simplified version. Full implementation will include:
        - KR-SBERT embedding generation
        - Vector similarity search
        - RNE graph expansion
        - Cross-law reference resolution

        Args:
            query: User query string
            top_k: Number of results to return

        Returns:
            List of relevant HANG nodes with metadata
        """
        logger.info(f"Searching domain {self.domain_id} for: {query}")

        # TODO: Phase 1 - Implement basic text search
        # TODO: Phase 2 - Add semantic search with KR-SBERT
        # TODO: Phase 3 - Add RNE graph expansion
        # TODO: Phase 4 - Add cross-law references

        # For now, return mock results for testing
        return self._mock_search_results(query)

    def _mock_search_results(self, query: str) -> list[dict]:
        """
        Mock search results for initial testing

        Args:
            query: User query

        Returns:
            Mock result list
        """
        # Simple Neo4j query to verify connection
        try:
            cypher_query = """
            MATCH (h:HANG)
            WHERE h.content CONTAINS $keyword
            RETURN h.hang_id AS hang_id,
                   h.content AS content,
                   h.law_name AS law_name,
                   h.jo_number AS jo_number,
                   h.hang_number AS hang_number
            LIMIT $limit
            """

            # Extract simple keyword from query (naive approach)
            keyword = query.replace("에 대해", "").replace("알려주세요", "").strip()

            results = self.neo4j_client.execute_query(
                cypher_query,
                {"keyword": keyword, "limit": 5}
            )

            if results:
                logger.info(f"Found {len(results)} results in Neo4j")
                return [
                    {
                        "hang_id": record["hang_id"],
                        "content": record["content"],
                        "law_name": record["law_name"],
                        "jo_number": record["jo_number"],
                        "hang_number": record["hang_number"],
                        "score": 0.8  # Mock score
                    }
                    for record in results
                ]
            else:
                logger.warning("No results found in Neo4j")
                return []

        except Exception as e:
            logger.error(f"Error searching Neo4j: {e}")
            return []

    def format_search_results(self, results: list[dict]) -> str:
        """
        Format search results for LLM consumption

        Args:
            results: List of search result dictionaries

        Returns:
            Formatted string for LLM context
        """
        if not results:
            return "관련 법률 조항을 찾을 수 없습니다."

        formatted = f"검색 결과 ({len(results)}개 조항):\n\n"

        for i, result in enumerate(results, 1):
            formatted += f"{i}. {result['law_name']} 제{result['jo_number']}조 제{result['hang_number']}항\n"
            formatted += f"   내용: {result['content'][:200]}...\n"
            formatted += f"   관련도: {result.get('score', 0):.2f}\n\n"

        return formatted

    def get_domain_stats(self) -> dict:
        """
        Get statistics about this domain

        Returns:
            Dictionary with domain statistics
        """
        try:
            # Count HANG nodes in this domain
            cypher_query = """
            MATCH (h:HANG)-[:BELONGS_TO]->(d:Domain {domain_id: $domain_id})
            RETURN count(h) as hang_count
            """

            results = self.neo4j_client.execute_query(
                cypher_query,
                {"domain_id": self.domain_id}
            )

            hang_count = results[0]["hang_count"] if results else 0

            return {
                "domain_id": self.domain_id,
                "domain_name": self.domain_name,
                "hang_count": hang_count,
                "status": "active"
            }

        except Exception as e:
            logger.error(f"Error getting domain stats: {e}")
            return {
                "domain_id": self.domain_id,
                "domain_name": self.domain_name,
                "hang_count": 0,
                "status": "error",
                "error": str(e)
            }
