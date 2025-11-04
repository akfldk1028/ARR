"""
Repository Layer

Data Access 추상화 (DIP 적용)

GraphRepository: 인터페이스 (ABC)
Neo4jGraphRepository: Neo4j 구현체
"""

from .graph_repository import GraphRepository
from .neo4j_repository import Neo4jGraphRepository

__all__ = ["GraphRepository", "Neo4jGraphRepository"]
