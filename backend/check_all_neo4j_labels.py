"""Check all node labels and relationships in Neo4j"""
from graph_db.services.neo4j_service import Neo4jService

def check_all_labels():
    service = Neo4jService()

    try:
        service.connect()
        print("[OK] Connected to Neo4j\n")

        # Get all node labels
        print("="*80)
        print("All Node Labels")
        print("="*80)

        labels_query = "CALL db.labels() YIELD label RETURN label"
        labels = service.execute_query(labels_query)

        for label_info in labels:
            label = label_info['label']

            # Count nodes for each label
            count_query = f"MATCH (n:{label}) RETURN count(n) as count"
            count_result = service.execute_query(count_query)
            count = count_result[0]['count'] if count_result else 0

            print(f"{label}: {count} nodes")

        # Get all relationship types
        print("\n" + "="*80)
        print("All Relationship Types")
        print("="*80)

        rel_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        rel_types = service.execute_query(rel_query)

        for rel_info in rel_types:
            rel_type = rel_info['relationshipType']

            # Count relationships for each type
            count_query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
            count_result = service.execute_query(count_query)
            count = count_result[0]['count'] if count_result else 0

            print(f"{rel_type}: {count} relationships")

        # Sample nodes from most common label
        print("\n" + "="*80)
        print("Sample Nodes")
        print("="*80)

        if labels:
            # Get most common label
            for label_info in labels[:3]:  # Check first 3 labels
                label = label_info['label']
                sample_query = f"""
                MATCH (n:{label})
                RETURN n
                LIMIT 3
                """
                samples = service.execute_query(sample_query)

                print(f"\n{label} samples:")
                for i, result in enumerate(samples, 1):
                    node = result['n']
                    print(f"\n  Sample {i}:")
                    for key, value in dict(node).items():
                        value_str = str(value)[:100]  # Limit length
                        print(f"    {key}: {value_str}")

    finally:
        service.disconnect()
        print("\n[OK] Disconnected from Neo4j")

if __name__ == "__main__":
    check_all_labels()
