"""
Neo4j Connection Test Script
Run this to verify your Neo4j database connection
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from graph.neo4j_connection import Neo4jConnection, initialize_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_connection():
    """Test Neo4j database connection and basic operations"""
    
    print("Testing Neo4j Connection...")
    print("=" * 50)
    
    try:
        # Initialize database
        print("1. Initializing database connection...")
        success = await initialize_database()
        
        if not success:
            print("Failed to connect to Neo4j database")
            print("\nMake sure:")
            print("   - Neo4j is running")
            print("   - Credentials are correct in .env file")
            print("   - Connection URI is accessible")
            return False
        
        print("Database connection successful!")
        
        # Get database stats
        print("\n2. Getting database statistics...")
        db = Neo4jConnection()
        if not db.connect():
            print("Failed to connect for stats")
            return False
        stats = db.get_database_stats()
        
        print(f"Database Statistics:")
        print(f"   - Total Nodes: {stats.get('total_nodes', 'N/A')}")
        print(f"   - Total Relationships: {stats.get('total_relationships', 'N/A')}")
        print(f"   - Node Labels: {', '.join(stats.get('node_labels', []))}")
        print(f"   - Relationship Types: {', '.join(stats.get('relationship_types', []))}")
        
        # Test basic operations
        print("\n3. Testing basic CRUD operations...")
        
        # Create test data
        create_query = """
        CREATE (test:TestNode {
            id: 'test-node-1',
            name: 'Neo4j Connection Test',
            timestamp: datetime(),
            test: true
        })
        RETURN test
        """
        
        result = db.execute_write_query(create_query)
        if result:
            print("CREATE operation successful")
        
        # Read test data
        read_query = "MATCH (test:TestNode {id: 'test-node-1'}) RETURN test"
        result = db.execute_query(read_query)
        if result:
            print("READ operation successful")
            print(f"   Found test node: {result[0]['test']['name']}")
        
        # Update test data
        update_query = """
        MATCH (test:TestNode {id: 'test-node-1'})
        SET test.updated = datetime()
        RETURN test
        """
        result = db.execute_write_query(update_query)
        if result:
            print("UPDATE operation successful")
        
        # Delete test data
        delete_query = "MATCH (test:TestNode {id: 'test-node-1'}) DELETE test"
        db.execute_write_query(delete_query)
        print("DELETE operation successful")
        
        # Test relationship creation
        print("\n4. Testing relationship operations...")
        
        relationship_query = """
        CREATE (u:TestUser {name: 'Alice'})
        CREATE (a:TestAgent {name: 'BookingAgent'})
        CREATE (u)-[r:TALKS_TO {timestamp: datetime()}]->(a)
        RETURN u, a, r
        """
        
        result = db.execute_write_query(relationship_query)
        if result:
            print("Relationship creation successful")
        
        # Query relationship
        query_relationship = """
        MATCH (u:TestUser)-[r:TALKS_TO]->(a:TestAgent)
        RETURN u.name as user, a.name as agent, r.timestamp as when
        """
        
        result = db.execute_query(query_relationship)
        if result:
            print("Relationship query successful")
            for record in result:
                print(f"   {record['user']} talks to {record['agent']} at {record['when']}")
        
        # Clean up test data
        cleanup_query = """
        MATCH (n) 
        WHERE n:TestUser OR n:TestAgent OR n:TestNode 
        DETACH DELETE n
        """
        db.execute_write_query(cleanup_query)
        print("Test data cleaned up")
        
        print("\nAll tests passed! Neo4j is ready for A2A integration.")
        return True
        
    except Exception as e:
        print(f"\nTest failed with error: {str(e)}")
        logger.exception("Test failed")
        return False
    
    finally:
        # Ensure cleanup
        try:
            from graph.neo4j_connection import shutdown_database
            await shutdown_database()
        except:
            pass

def main():
    """Main test function"""
    print("Starting Neo4j + A2A Integration Tests")
    print(f"Project Root: {project_root}")
    
    # Check if .env file exists
    env_file = project_root / ".env"
    if not env_file.exists():
        print("\nWARNING: .env file not found!")
        print(f"   Please copy .env.example to .env and configure your settings")
        print(f"   Expected location: {env_file}")
        return False
    
    # Run async test
    try:
        success = asyncio.run(test_connection())
        return success
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)