"""
Phase 1.1: Database State Verification

Validates current Neo4j database state before implementing JO embeddings:
- Total JO nodes
- JO nodes without HANG children (invisible to current search)
- Critical test case: 용도지역 (Article 36)
"""
import sys
from pathlib import Path

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from neo4j_client import get_neo4j_client


def verify_jo_nodes():
    """Verify total JO nodes and their embedding status"""
    neo4j = get_neo4j_client()
    session = neo4j.get_session()

    # Open output file
    output_path = Path(__file__).parent / "verification_results.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        def log(msg):
            f.write(msg + '\n')
            print(msg)

        log("=" * 80)
        log("Phase 1.1: Database State Verification")
        log("=" * 80)

        # 1. Count total JO nodes
        log("\n[1] Total JO Nodes")
        log("-" * 80)

        query = """
        MATCH (jo:JO)
        RETURN count(jo) as total_jo_nodes,
               count(jo.embedding) as jos_with_embedding,
               count(jo) - count(jo.embedding) as jos_without_embedding
        """

        result = session.run(query).single()
        total = result['total_jo_nodes']
        with_emb = result['jos_with_embedding']
        without_emb = result['jos_without_embedding']

        log(f"Total JO nodes: {total}")
        log(f"JO nodes with embeddings: {with_emb}")
        log(f"JO nodes without embeddings: {without_emb}")

        if without_emb == total:
            log("[OK] Confirmed: NO JO nodes have embeddings (expected)")
        elif with_emb > 0:
            log(f"[WARNING] Unexpected: {with_emb} JO nodes already have embeddings")

        # 2. Identify JO nodes without HANG children
        log("\n[2] JO Nodes Without HANG Children (Currently Invisible)")
        log("-" * 80)

        query = """
        MATCH (jo:JO)
        WHERE NOT EXISTS((jo)-[:CONTAINS]->(:HANG))
        RETURN count(jo) as invisible_count
        """

        result = session.run(query).single()
        invisible_count = result['invisible_count']

        log(f"JO nodes without HANG children: {invisible_count}")
        log(f"Impact: {invisible_count}/{total} ({invisible_count/total*100:.1f}%) articles are INVISIBLE to current search")

        # Get sample invisible JOs
        query = """
        MATCH (jo:JO)
        WHERE NOT EXISTS((jo)-[:CONTAINS]->(:HANG))
        RETURN jo.full_id, jo.title
        ORDER BY jo.full_id
        LIMIT 10
        """

        results = session.run(query)
        log(f"\nSample invisible JO nodes (first 10):")
        for i, record in enumerate(results, 1):
            log(f"  {i}. {record['jo.full_id']}")
            log(f"     {record['jo.title']}")

        # 3. Critical test case: 용도지역 (Article 36)
        log("\n[3] Critical Test Case: 용도지역 (Article 36)")
        log("-" * 80)

        query = """
        MATCH (jo:JO)
        WHERE jo.title CONTAINS "용도지역"
        RETURN jo.full_id,
               jo.title,
               EXISTS((jo)-[:CONTAINS]->(:HANG)) as has_hang,
               size([(jo)-[:CONTAINS]->(h:HANG) | h]) as hang_count
        ORDER BY jo.full_id
        """

        results = session.run(query)
        articles = list(results)

        log(f"Found {len(articles)} articles containing '용도지역':\n")

        correct_article = None
        appendix_article = None

        for record in articles:
            full_id = record['jo.full_id']
            title = record['jo.title']
            has_hang = record['has_hang']
            hang_count = record['hang_count']

            # Determine if this is main content or appendix
            is_main = '::제4장::' in full_id or '::제3장::' in full_id
            is_appendix = '::제12장::' in full_id

            status = "[MAIN CONTENT]" if is_main else "[APPENDIX]" if is_appendix else "[UNKNOWN]"
            visibility = f"VISIBLE ({hang_count} HANGs)" if has_hang else "INVISIBLE (no HANGs)"

            log(f"{status} | {visibility}")
            log(f"  ID: {full_id}")
            log(f"  Title: {title}")

            if is_main:
                correct_article = record
            if is_appendix:
                appendix_article = record

            # Show sample HANG content if available
            if has_hang:
                hang_query = """
                MATCH (jo:JO {full_id: $jo_id})-[:CONTAINS]->(h:HANG)
                RETURN h.content
                LIMIT 2
                """
                hang_results = session.run(hang_query, {'jo_id': full_id})
                log(f"  Sample HANG content:")
                for hang in hang_results:
                    content = hang['h.content']
                    log(f"    - {content[:80]}...")

            log("")

        # 4. Problem analysis
        log("\n[4] Problem Analysis")
        log("-" * 80)

        if correct_article and not correct_article['has_hang']:
            log("[CRITICAL ISSUE CONFIRMED]")
            log(f"   The correct article (제4장 제36조) has NO HANG children")
            log(f"   --> Currently INVISIBLE to search")
            log("")

        if appendix_article and appendix_article['has_hang']:
            log("[SEARCH MISDIRECTION CONFIRMED]")
            log(f"   The appendix article (제12장) has {appendix_article['hang_count']} HANG children")
            log(f"   --> Currently VISIBLE and being returned instead of correct article")
            log("")

        if correct_article and not correct_article['has_hang'] and appendix_article and appendix_article['has_hang']:
            log("[ROOT CAUSE IDENTIFIED]")
            log("   Current system only searches HANG nodes")
            log("   --> Correct article (제4장::제36조) invisible --> skipped")
            log("   --> Appendix article (제12장::제36조) visible --> returned (WRONG)")
            log("")
            log("[SOLUTION]")
            log("   Add JO-level embeddings --> Make ALL articles searchable")
            log("   Add path scoring --> Penalize 제12장 (appendix)")
            log("   --> Correct article will be found and ranked higher")

        session.close()

        log("\n" + "=" * 80)
        log("Verification Complete")
        log(f"Results saved to: {output_path}")
        log("=" * 80)


if __name__ == "__main__":
    try:
        verify_jo_nodes()
    except Exception as e:
        print(f"\n[ERROR] during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
