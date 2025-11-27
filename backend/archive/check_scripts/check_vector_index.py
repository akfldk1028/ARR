"""
Check Neo4j Vector Index
"""
from neo4j import GraphDatabase

def check_vector_index():
    uri = "neo4j://127.0.0.1:7687"
    user = "neo4j"
    password = "11111111"

    print("=" * 60)
    print("Vector Index Check")
    print("=" * 60)

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # Check all indexes
        result = session.run("SHOW INDEXES")
        print("\n[1] All Indexes:")
        for record in result:
            print(f"    - {record['name']}: {record['type']} on {record['labelsOrTypes']}")

        # Check vector indexes specifically
        result = session.run("SHOW INDEXES WHERE type = 'VECTOR'")
        vector_indexes = list(result)
        print(f"\n[2] Vector Indexes: {len(vector_indexes)} found")
        for record in vector_indexes:
            print(f"    - {record['name']}")
            print(f"      Labels: {record['labelsOrTypes']}")
            print(f"      Properties: {record['properties']}")

        # Check if hang_embedding_idx exists
        result = session.run("""
            SHOW INDEXES WHERE name = 'hang_embedding_idx'
        """)
        hang_idx = list(result)
        if hang_idx:
            print(f"\n[3] hang_embedding_idx: EXISTS")
            idx = hang_idx[0]
            print(f"    Type: {idx['type']}")
            print(f"    State: {idx['state']}")
        else:
            print(f"\n[3] hang_embedding_idx: NOT FOUND")
            print("    Need to create vector index!")

    driver.close()

if __name__ == "__main__":
    check_vector_index()
