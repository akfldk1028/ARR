"""
Neo4j Database Auto Reset (No Confirmation)
Clear all data and reinitialize indexes
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services import get_neo4j_service

def main():
    print("=" * 60)
    print("NEO4J DATABASE AUTO-RESET")
    print("=" * 60)

    # Get Neo4j service
    neo4j = get_neo4j_service()

    # 1. Check current state
    print("\n[STEP 1] Checking current database state...")
    count_query = """
    MATCH (n)
    RETURN labels(n)[0] as label, count(n) as count
    ORDER BY label
    """
    results = neo4j.execute_query(count_query)

    if results:
        print("\nCurrent node counts:")
        for record in results:
            label = record.get('label', 'Unknown')
            count = record.get('count', 0)
            print(f"  {label}: {count}")
    else:
        print("  Database is empty")

    # 2. Delete all data
    print("\n[STEP 2] Deleting all nodes and relationships...")
    delete_query = "MATCH (n) DETACH DELETE n"
    neo4j.execute_write_query(delete_query)
    print("  OK All data deleted")

    # 3. Verify deletion
    print("\n[STEP 3] Verifying deletion...")
    verify_query = "MATCH (n) RETURN count(n) as count"
    result = neo4j.execute_query(verify_query)
    count = result[0]['count'] if result else 0

    if count == 0:
        print(f"  OK {count} nodes remaining (clean)")
    else:
        print(f"  WARNING {count} nodes remaining (expected 0)")

    # 4. Recreate indexes
    print("\n[STEP 4] Recreating indexes and constraints...")

    indexes = [
        # Session indexes
        "CREATE INDEX session_id IF NOT EXISTS FOR (s:Session) ON (s.session_id)",
        "CREATE INDEX session_created IF NOT EXISTS FOR (s:Session) ON (s.created_at)",

        # Turn indexes
        "CREATE INDEX turn_sequence IF NOT EXISTS FOR (t:Turn) ON (t.sequence)",
        "CREATE INDEX turn_created IF NOT EXISTS FOR (t:Turn) ON (t.created_at)",

        # Message indexes
        "CREATE INDEX message_created IF NOT EXISTS FOR (m:Message) ON (m.timestamp)",

        # AgentExecution indexes
        "CREATE INDEX agent_execution_started IF NOT EXISTS FOR (ae:AgentExecution) ON (ae.started_at)",
        "CREATE INDEX agent_execution_agent IF NOT EXISTS FOR (ae:AgentExecution) ON (ae.agent_slug)",

        # Decision indexes
        "CREATE INDEX decision_timestamp IF NOT EXISTS FOR (d:Decision) ON (d.timestamp)",

        # Task indexes
        "CREATE INDEX task_status IF NOT EXISTS FOR (t:Task) ON (t.status)",
        "CREATE INDEX task_created IF NOT EXISTS FOR (t:Task) ON (t.created_at)",

        # Artifact indexes
        "CREATE INDEX artifact_type IF NOT EXISTS FOR (a:Artifact) ON (a.artifact_type)",
        "CREATE INDEX artifact_created IF NOT EXISTS FOR (a:Artifact) ON (a.created_at)",
    ]

    created_count = 0
    for index_query in indexes:
        try:
            neo4j.execute_write_query(index_query)
            created_count += 1
        except Exception as e:
            print(f"  Warning: {str(e)}")

    print(f"  OK {created_count}/{len(indexes)} indexes created")

    # 5. Final statistics
    print("\n[STEP 5] Database Statistics:")
    print("=" * 60)

    stats_queries = {
        "Total Nodes": "MATCH (n) RETURN count(n) as count",
        "Total Relationships": "MATCH ()-[r]->() RETURN count(r) as count",
        "Sessions": "MATCH (s:Session) RETURN count(s) as count",
        "Turns": "MATCH (t:Turn) RETURN count(t) as count",
        "Messages": "MATCH (m:Message) RETURN count(m) as count",
        "AgentExecutions": "MATCH (ae:AgentExecution) RETURN count(ae) as count",
        "Decisions": "MATCH (d:Decision) RETURN count(d) as count",
        "Tasks": "MATCH (t:Task) RETURN count(t) as count",
        "Artifacts": "MATCH (a:Artifact) RETURN count(a) as count",
    }

    for label, query in stats_queries.items():
        result = neo4j.execute_query(query)
        count = result[0]['count'] if result else 0
        print(f"  {label}: {count}")

    print("\n" + "=" * 60)
    print("OK Neo4j database reset complete")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
