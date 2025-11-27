"""
Complete Law Search System Pipeline Verification

Checks:
1. PDF -> JSON parsing
2. JSON -> Neo4j loading
3. Embeddings (node + relationship)
4. RNE/INE algorithms
5. Multi-Agent System (MAS)
"""

from graph_db.services.neo4j_service import Neo4jService
from pathlib import Path
import json

def verify_pipeline():
    print("="*80)
    print("LAW SEARCH SYSTEM - FULL PIPELINE VERIFICATION")
    print("="*80)

    # Step 1: PDF -> JSON
    print("\n[STEP 1] PDF -> JSON Parsing")
    print("-" * 80)

    parsed_dir = Path("law/data/parsed")
    json_files = list(parsed_dir.glob("*.json"))

    print(f"Found {len(json_files)} JSON files:")
    for f in json_files:
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
            law_type = data['law_info']['law_type']
            total_units = data['law_info']['total_units']
            print(f"  - {f.name}")
            print(f"    Type: {law_type}, Units: {total_units}")

    if len(json_files) == 3:
        print("[OK] Step 1: PDF -> JSON parsing complete")
    else:
        print(f"[WARN] Expected 3 files, found {len(json_files)}")

    # Step 2: JSON -> Neo4j
    print("\n[STEP 2] JSON -> Neo4j Loading")
    print("-" * 80)

    service = Neo4jService()
    service.connect()

    try:
        # Check LAW nodes
        law_query = """
        MATCH (law:LAW)
        RETURN law.name as name, law.law_type as law_type, law.full_id as full_id
        ORDER BY law.law_type
        """
        laws = service.execute_query(law_query)

        print(f"LAW nodes: {len(laws)}")
        for law in laws:
            print(f"  - {law.get('law_type', 'NO_TYPE')}: {law['full_id']}")

        # Check JO, HANG, HO nodes
        stats_query = """
        MATCH (n)
        WHERE n:JO OR n:HANG OR n:HO
        RETURN labels(n)[0] as label, count(*) as count
        ORDER BY label
        """
        stats = service.execute_query(stats_query)

        print("\nNode statistics:")
        for stat in stats:
            print(f"  {stat['label']}: {stat['count']} nodes")

        # Check CONTAINS relationships
        rel_query = """
        MATCH ()-[r:CONTAINS]->()
        RETURN count(r) as count
        """
        rel_count = service.execute_query(rel_query)[0]['count']
        print(f"\nCONTAINS relationships: {rel_count}")

        if len(laws) == 3 and rel_count > 0:
            print("[OK] Step 2: Neo4j loading complete")
        else:
            print(f"[WARN] Issues detected in Neo4j data")

        # Step 3: Embeddings
        print("\n[STEP 3] Embeddings (Node + Relationship)")
        print("-" * 80)

        # Check HANG node embeddings
        hang_emb_query = """
        MATCH (h:HANG)
        WHERE h.embedding IS NOT NULL
        RETURN count(h) as with_emb,
               size(h.embedding) as emb_size
        LIMIT 1
        """
        hang_emb = service.execute_query(hang_emb_query)

        if hang_emb and hang_emb[0]['with_emb'] > 0:
            emb_size = hang_emb[0]['emb_size']
            total_hang = service.execute_query("MATCH (h:HANG) RETURN count(h) as count")[0]['count']
            with_emb = hang_emb[0]['with_emb']

            print(f"HANG node embeddings:")
            print(f"  Total HANG nodes: {total_hang}")
            print(f"  With embeddings: {with_emb}")
            print(f"  Embedding size: {emb_size}")

            if with_emb == total_hang:
                print("[OK] All HANG nodes have embeddings")
            else:
                print(f"[WARN] {total_hang - with_emb} HANG nodes missing embeddings")
        else:
            print("[ERROR] No HANG embeddings found!")

        # Check CONTAINS relationship embeddings
        rel_emb_query = """
        MATCH ()-[r:CONTAINS]->()
        WHERE r.embedding IS NOT NULL
        RETURN count(r) as with_emb,
               size(r.embedding) as emb_size
        LIMIT 1
        """
        rel_emb = service.execute_query(rel_emb_query)

        if rel_emb and rel_emb[0]['with_emb'] > 0:
            total_rels = rel_count
            with_emb = rel_emb[0]['with_emb']
            emb_size = rel_emb[0]['emb_size']

            print(f"\nCONTAINS relationship embeddings:")
            print(f"  Total relationships: {total_rels}")
            print(f"  With embeddings: {with_emb}")
            print(f"  Embedding size: {emb_size}")

            if with_emb == total_rels:
                print("[OK] All relationships have embeddings")
            else:
                print(f"[WARN] {total_rels - with_emb} relationships missing embeddings")
        else:
            print("[ERROR] No relationship embeddings found!")

        # Step 4: RNE/INE Algorithm
        print("\n[STEP 4] RNE/INE Algorithm")
        print("-" * 80)

        # Check if RNE functions exist
        try:
            from agents.law.domain_agent import DomainAgent
            print("DomainAgent imported successfully")

            # Check for RNE-related methods
            agent_methods = dir(DomainAgent)
            rne_methods = [m for m in agent_methods if 'rne' in m.lower() or 'expand' in m.lower()]

            if rne_methods:
                print(f"Found RNE-related methods: {rne_methods}")
                print("[OK] RNE implementation exists")
            else:
                print("[WARN] No RNE-specific methods found")

        except Exception as e:
            print(f"[ERROR] Could not verify RNE: {e}")

        # Step 5: Multi-Agent System
        print("\n[STEP 5] Multi-Agent System (MAS)")
        print("-" * 80)

        # Check Domain table
        domain_query = """
        SELECT domain_id, domain_name, is_active
        FROM law_domain
        ORDER BY domain_id
        """

        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(domain_query)
                domains = cursor.fetchall()

                print(f"Domain agents: {len(domains)}")
                for domain in domains:
                    domain_id, name, is_active = domain
                    status = "ACTIVE" if is_active else "INACTIVE"
                    print(f"  - {name} ({status})")

                if len(domains) >= 5:
                    print("[OK] Domain agents initialized")
                else:
                    print(f"[WARN] Expected 5+ domains, found {len(domains)}")
        except Exception as e:
            print(f"[ERROR] Could not check domains: {e}")

        # Check A2A protocol
        print("\nA2A Protocol:")
        try:
            from agents.law.agent_manager import AgentManager
            print("  AgentManager imported successfully")
            print("[OK] A2A components available")
        except Exception as e:
            print(f"[ERROR] A2A import failed: {e}")

    finally:
        service.disconnect()

    # Final Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print("""
Pipeline Status:
  [1] PDF -> JSON Parsing:        Check output above
  [2] JSON -> Neo4j Loading:      Check output above
  [3] Node Embeddings:            Check output above
  [4] Relationship Embeddings:    Check output above
  [5] RNE/INE Algorithm:          Check output above
  [6] Multi-Agent System:         Check output above
    """)

if __name__ == "__main__":
    verify_pipeline()
