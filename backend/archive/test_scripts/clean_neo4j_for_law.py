"""
Neo4j 정리 스크립트 - Law 관련 데이터 삭제
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv('NEO4J_URI', 'neo4j://127.0.0.1:7687')
user = os.getenv('NEO4J_USER', 'neo4j')
password = os.getenv('NEO4J_PASSWORD')

print("=" * 60)
print("NEO4J LAW DATA CLEANUP")
print("=" * 60)

driver = GraphDatabase.driver(uri, auth=(user, password))

def clean_law_data(tx):
    """Law 관련 노드 모두 삭제"""
    # Law 관련 노드 라벨들
    law_labels = ['LAW', 'PYEON', 'JANG', 'JEOL', 'GWAN', 'JO', 'HANG', 'HO', 'MOK']

    total_deleted = 0

    for label in law_labels:
        result = tx.run(f"MATCH (n:{label}) DETACH DELETE n RETURN count(n) as deleted")
        record = result.single()
        if record:
            deleted = record['deleted']
            if deleted > 0:
                print(f"  Deleted {deleted} {label} nodes")
                total_deleted += deleted

    return total_deleted

def check_law_nodes(tx):
    """Law 관련 노드 개수 확인"""
    law_labels = ['LAW', 'PYEON', 'JANG', 'JEOL', 'GWAN', 'JO', 'HANG', 'HO', 'MOK']

    counts = {}
    total = 0

    for label in law_labels:
        result = tx.run(f"MATCH (n:{label}) RETURN count(n) as count")
        record = result.single()
        if record:
            count = record['count']
            counts[label] = count
            total += count

    return counts, total

try:
    # 정리 전 상태 확인
    print("\n[1] Checking existing law nodes...")
    with driver.session() as session:
        counts_before, total_before = session.execute_read(check_law_nodes)

        if total_before > 0:
            print(f"\n  Found {total_before} law-related nodes:")
            for label, count in counts_before.items():
                if count > 0:
                    print(f"    - {label}: {count}")
        else:
            print("  No law nodes found (database is clean)")

    # 정리 실행
    if total_before > 0:
        print("\n[2] Cleaning law nodes...")
        with driver.session() as session:
            deleted = session.execute_write(clean_law_data)
            print(f"\n  Total deleted: {deleted} nodes")

        # 정리 후 확인
        print("\n[3] Verifying cleanup...")
        with driver.session() as session:
            counts_after, total_after = session.execute_read(check_law_nodes)

            if total_after == 0:
                print("  [OK] All law nodes deleted successfully")
            else:
                print(f"  [WARNING] {total_after} nodes still remaining")

    print("\n" + "=" * 60)
    print("NEO4J CLEANUP COMPLETED")
    print("=" * 60)

except Exception as e:
    print(f"\n[ERROR] Failed to clean Neo4j: {e}")
finally:
    driver.close()
