"""
Shared Neo4j client for all domain agents

Provides singleton connection to Neo4j graph database.
"""

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j database client with connection pooling"""

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")

        if not password:
            raise ValueError("NEO4J_PASSWORD environment variable is required")

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Neo4j client initialized: {uri}")

        # Test connection
        try:
            self.driver.verify_connectivity()
            logger.info("Neo4j connection verified successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Close the Neo4j driver connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def get_session(self):
        """Get a new Neo4j session"""
        return self.driver.session()

    def execute_query(self, query: str, parameters: dict = None):
        """
        Execute a Cypher query and return results

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records
        """
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record for record in result]


# Singleton instance
_neo4j_client = None


def get_neo4j_client() -> Neo4jClient:
    """
    Get the singleton Neo4j client instance

    Returns:
        Neo4jClient instance
    """
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client


def get_neo4j_session():
    """
    Get a new Neo4j session

    Returns:
        Neo4j session object
    """
    client = get_neo4j_client()
    return client.get_session()
