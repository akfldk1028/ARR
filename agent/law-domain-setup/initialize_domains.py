"""
Law Structure-Based Domain Initialization

2025 Best Practice:
- ChatLaw: Domain experts precisely define problem relationships
- AGENTiGraph: Pre-defined entity clusters
- Korean Legal NLP: Manual labeling by domain experts

Usage:
    python agent/law-domain-setup/initialize_domains.py
"""

import sys
from pathlib import Path

# Add law-domain-agents/shared to path for neo4j_client
agent_root = Path(__file__).parent.parent
sys.path.insert(0, str(agent_root / "law-domain-agents" / "shared"))

from neo4j_client import get_neo4j_client
from datetime import datetime
import uuid


# Domain definitions (matches FastAPI DomainManager slug_map)
DOMAINS = [
    {
        "domain_id": "land_use_zones",
        "domain_name": "용도지역",
        "slug": "land_use_zones",
        "description": "용도지역, 용도지구, 용도구역에 관한 규정 (제4장)",
        "rules": [
            # 제4장 용도지역 관련
            lambda fid: "제4장" in fid and any(x in fid for x in ["제36조", "제37조", "제38조", "제39조", "제40조", "제41조", "제42조"]),
            # 키워드 기반
            lambda fid: any(x in fid for x in ["용도지역", "도시지역", "관리지역", "농림지역", "자연환경보전지역"]),
        ]
    },
    {
        "domain_id": "development_activities",
        "domain_name": "개발행위",
        "slug": "development_activities",
        "description": "개발행위 허가 및 제한에 관한 규정",
        "rules": [
            # 개발행위 키워드
            lambda fid: "개발행위" in fid,
            lambda fid: "개발" in fid and "허가" in fid,
        ]
    },
    {
        "domain_id": "land_transactions",
        "domain_name": "토지거래",
        "slug": "land_transactions",
        "description": "토지거래 허가 및 제한에 관한 규정",
        "rules": [
            # 토지거래 키워드
            lambda fid: "토지거래" in fid,
            lambda fid: "토지" in fid and "거래" in fid,
        ]
    },
    {
        "domain_id": "urban_planning",
        "domain_name": "도시계획 및 이용",
        "slug": "urban_planning",
        "description": "도시계획 및 도시계획시설에 관한 규정",
        "rules": [
            # 도시계획 키워드
            lambda fid: "도시계획" in fid,
            lambda fid: "도시계획시설" in fid,
            # 제3장, 제6장 등
            lambda fid: any(x in fid for x in ["제3장", "제6장"]),
        ]
    },
    {
        "domain_id": "urban_development",
        "domain_name": "도시개발",
        "slug": "urban_development",
        "description": "도시개발 및 정비에 관한 규정",
        "rules": [
            # 도시개발 키워드
            lambda fid: "도시개발" in fid,
            lambda fid: "정비" in fid,
        ]
    },
]


def classify_hang(full_id: str) -> str:
    """
    Classify HANG node to domain based on full_id analysis

    Args:
        full_id: HANG node's full_id

    Returns:
        domain_id (land_use_zones, development_activities, etc.)
    """
    for domain in DOMAINS:
        for rule in domain["rules"]:
            if rule(full_id):
                return domain["domain_id"]

    # Default: land_use_zones domain (most common)
    return "land_use_zones"


def main():
    print("=" * 80)
    print("Law Structure-Based Domain Initialization")
    print("=" * 80)
    print("\n2025 Best Practice:")
    print("- ChatLaw: Domain experts precisely define problem relationships")
    print("- AGENTiGraph: Pre-defined entity clusters")
    print("- Law structure and keyword-based domain classification\n")

    # Neo4j connection
    print("[1/5] Connecting to Neo4j...")
    client = get_neo4j_client()
    session = client.get_session()

    # Delete existing Domain nodes (clean start)
    print("[2/5] Deleting existing Domain nodes...")
    session.run("MATCH (d:Domain) DETACH DELETE d")
    print("  > Existing domains deleted")

    # Load all HANG nodes
    print("[3/5] Loading HANG nodes...")
    query = """
    MATCH (h:HANG)
    RETURN h.full_id as full_id
    """
    results = session.run(query)
    hang_nodes = [r["full_id"] for r in results]
    print(f"  > Loaded {len(hang_nodes)} HANG nodes")

    # Classify HANG nodes by domain
    print("[4/5] Classifying HANG nodes by domain...")
    domain_assignments = {}
    for domain in DOMAINS:
        domain_assignments[domain["domain_id"]] = []

    for full_id in hang_nodes:
        domain_id = classify_hang(full_id)
        domain_assignments[domain_id].append(full_id)

    # Print distribution statistics
    print("\n  Domain distribution:")
    for domain in DOMAINS:
        count = len(domain_assignments[domain["domain_id"]])
        print(f"    - {domain['domain_name']}: {count} nodes")

    # Create Domain nodes and relationships
    print("\n[5/5] Creating Domain nodes and relationships...")

    created_at = datetime.now().isoformat()

    for domain in DOMAINS:
        domain_id = domain["domain_id"]
        hang_ids = domain_assignments[domain_id]

        if not hang_ids:
            print(f"  ! WARNING: {domain['domain_name']}: No HANG nodes assigned, skipping")
            continue

        # Domain 노드 생성
        create_domain_query = """
        CREATE (d:Domain {
            domain_id: $domain_id,
            domain_name: $domain_name,
            description: $description,
            node_count: $node_count,
            created_at: $created_at,
            updated_at: $updated_at
        })
        """

        session.run(create_domain_query, {
            "domain_id": domain_id,
            "domain_name": domain["domain_name"],
            "description": domain["description"],
            "node_count": len(hang_ids),
            "created_at": created_at,
            "updated_at": created_at
        })

        # BELONGS_TO_DOMAIN 관계 생성 (배치 처리)
        create_relations_query = """
        UNWIND $hang_ids as hang_id
        MATCH (h:HANG {full_id: hang_id})
        MATCH (d:Domain {domain_id: $domain_id})
        CREATE (h)-[:BELONGS_TO_DOMAIN]->(d)
        """

        session.run(create_relations_query, {
            "hang_ids": hang_ids,
            "domain_id": domain_id
        })

        print(f"  > OK: {domain['domain_name']}: {len(hang_ids)} nodes assigned")

    session.close()

    # Final verification
    print("\n" + "=" * 80)
    print("Initialization Complete!")
    print("=" * 80)

    session = client.get_session()

    # Domain 노드 수 확인
    domain_count_result = session.run("MATCH (d:Domain) RETURN count(d) as count")
    domain_count = domain_count_result.single()["count"]

    # 관계 수 확인
    rel_count_result = session.run("MATCH ()-[r:BELONGS_TO_DOMAIN]->() RETURN count(r) as count")
    rel_count = rel_count_result.single()["count"]

    print(f"\nFinal Statistics:")
    print(f"  - Domain nodes: {domain_count}")
    print(f"  - BELONGS_TO_DOMAIN relationships: {rel_count}")

    # Domain details
    print(f"\nDomain Details:")
    detail_query = """
    MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d:Domain)
    RETURN d.domain_name as domain_name, count(h) as size
    ORDER BY size DESC
    """
    details = session.run(detail_query)
    for d in details:
        print(f"  - {d['domain_name']}: {d['size']} HANG nodes")

    session.close()

    print("\n" + "=" * 80)
    print("SUCCESS! Restart FastAPI server to see domains_loaded > 0")
    print("=" * 80)
    print("\nNext Steps:")
    print("  1. Restart FastAPI server")
    print("  2. Check http://localhost:8011/status")
    print("  3. Test search query")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
