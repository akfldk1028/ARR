"""
Neo4j Database Connection Manager
Handles connection, authentication, and basic operations
"""

import os
import logging
from typing import Optional, Dict, Any, List
from neo4j import GraphDatabase, Driver, Session
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Neo4jConnection:
    """Neo4j database connection and operations manager"""
    
    def __init__(self, uri: str = None, user: str = None, password: str = None, database: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        
        self._driver: Optional[Driver] = None
        self._session: Optional[Session] = None
        
    def connect(self) -> bool:
        """Establish connection to Neo4j database"""
        try:
            self._driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.user, self.password)
            )
            
            # Test connection
            with self._driver.session() as session:
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]
                
            if test_value == 1:
                logger.info(f"✅ Successfully connected to Neo4j at {self.uri}")
                return True
            else:
                logger.error("❌ Failed to verify Neo4j connection")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error connecting to Neo4j: {str(e)}")
            return False
    
    def disconnect(self):
        """Close the database connection"""
        if self._session:
            self._session.close()
            self._session = None
            
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("🔌 Disconnected from Neo4j")
    
    def get_session(self) -> Session:
        """Get a new database session"""
        if not self._driver:
            raise RuntimeError("Not connected to database. Call connect() first.")
        return self._driver.session(database=self.database)
    
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """Execute a Cypher query and return results"""
        try:
            with self.get_session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"❌ Error executing query: {str(e)}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    def execute_write_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """Execute a write query (CREATE, UPDATE, DELETE)"""
        try:
            with self.get_session() as session:
                def _execute_transaction(tx):
                    result = tx.run(query, parameters or {})
                    return [record.data() for record in result]
                
                return session.write_transaction(_execute_transaction)
        except Exception as e:
            logger.error(f"❌ Error executing write query: {str(e)}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    def clear_database(self) -> bool:
        """⚠️  WARNING: This will delete all data in the database!"""
        try:
            query = "MATCH (n) DETACH DELETE n"
            self.execute_write_query(query)
            logger.warning("🗑️ Database cleared - all nodes and relationships deleted")
            return True
        except Exception as e:
            logger.error(f"❌ Error clearing database: {str(e)}")
            return False
    
    def create_indexes(self):
        """Create necessary indexes for performance"""
        indexes = [
            "CREATE INDEX user_session_idx IF NOT EXISTS FOR (u:User) ON (u.session_id)",
            "CREATE INDEX agent_name_idx IF NOT EXISTS FOR (a:Agent) ON (a.name)",
            "CREATE INDEX conversation_id_idx IF NOT EXISTS FOR (c:Conversation) ON (c.conversation_id)",
            "CREATE INDEX message_timestamp_idx IF NOT EXISTS FOR (m:Message) ON (m.timestamp)",
        ]
        
        for index_query in indexes:
            try:
                self.execute_write_query(index_query)
                logger.info(f"✅ Index created: {index_query}")
            except Exception as e:
                logger.warning(f"⚠️ Index creation warning: {str(e)}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get basic database statistics"""
        queries = {
            "total_nodes": "MATCH (n) RETURN count(n) as count",
            "total_relationships": "MATCH ()-[r]->() RETURN count(r) as count",
            "node_labels": "CALL db.labels()",
            "relationship_types": "CALL db.relationshipTypes()"
        }
        
        stats = {}
        try:
            for key, query in queries.items():
                if key in ["total_nodes", "total_relationships"]:
                    result = self.execute_query(query)
                    stats[key] = result[0]["count"] if result else 0
                else:
                    result = self.execute_query(query)
                    stats[key] = [record[list(record.keys())[0]] for record in result]
                    
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {str(e)}")
            stats["error"] = str(e)
            
        return stats

# Global connection instance
neo4j_db = Neo4jConnection()

async def initialize_database():
    """Initialize database connection and setup"""
    if neo4j_db.connect():
        neo4j_db.create_indexes()
        stats = neo4j_db.get_database_stats()
        logger.info(f"📊 Database stats: {stats}")
        return True
    return False

async def shutdown_database():
    """Gracefully shutdown database connection"""
    neo4j_db.disconnect()