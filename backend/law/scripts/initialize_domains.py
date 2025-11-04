"""
Domain Initialization Script

기존 Neo4j HANG 노드들을 도메인별로 자동 클러스터링하여
AgentManager 도메인 생성 및 Neo4j 시각화 활성화

실행:
    python law/scripts/initialize_domains.py

기능:
    1. Neo4j에서 모든 HANG 노드의 임베딩 로드
    2. K-means 클러스터링으로 5-7개 도메인 생성
    3. AgentManager를 통해 도메인 생성 (자동으로 Neo4j 동기화)
    4. 완료 후 Neo4j Browser에서 시각화 가능
"""

import os
import sys
import django
import numpy as np
from sklearn.cluster import KMeans
import logging

# Django 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law import AgentManager
from graph_db.services import get_neo4j_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def load_all_hang_embeddings():
    """
    Neo4j에서 모든 HANG 노드의 임베딩 로드

    Returns:
        (hang_ids, embeddings) 튜플
    """
    logger.info("Loading HANG embeddings from Neo4j...")

    neo4j = get_neo4j_service()

    query = """
    MATCH (h:HANG)
    WHERE h.embedding IS NOT NULL
    RETURN h.full_id AS hang_id, h.embedding AS embedding
    ORDER BY h.full_id
    """

    results = neo4j.execute_query(query, {})

    hang_ids = []
    embeddings = []

    for record in results:
        hang_ids.append(record['hang_id'])
        embeddings.append(np.array(record['embedding']))

    logger.info(f"Loaded {len(hang_ids)} HANG nodes with embeddings")

    return hang_ids, np.array(embeddings)


def cluster_hangs(embeddings, n_clusters=5):
    """
    K-means 클러스터링으로 HANG 노드 분류

    Args:
        embeddings: HANG 임베딩 배열
        n_clusters: 생성할 도메인 개수 (기본 5개)

    Returns:
        클러스터 레이블 배열
    """
    logger.info(f"Clustering {len(embeddings)} nodes into {n_clusters} domains...")

    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=42,
        n_init=10,
        max_iter=300
    )

    labels = kmeans.fit_predict(embeddings)

    # 클러스터 크기 출력
    for i in range(n_clusters):
        count = np.sum(labels == i)
        logger.info(f"  Cluster {i}: {count} nodes")

    return labels


def create_domains_via_agent_manager(hang_ids, embeddings, labels, n_clusters):
    """
    AgentManager를 통해 도메인 생성

    AgentManager._create_new_domain()을 호출하면
    자동으로 Neo4j에 Domain 노드와 BELONGS_TO_DOMAIN 관계 생성됨

    Args:
        hang_ids: HANG ID 리스트
        embeddings: 임베딩 배열
        labels: 클러스터 레이블
        n_clusters: 클러스터 개수
    """
    logger.info("Initializing AgentManager...")

    # AgentManager 초기화 (빈 상태로 시작)
    manager = AgentManager()

    logger.info(f"Creating {n_clusters} domains...")

    for cluster_id in range(n_clusters):
        # 이 클러스터에 속한 노드들
        cluster_mask = labels == cluster_id
        cluster_hang_ids = [hang_ids[i] for i in range(len(hang_ids)) if cluster_mask[i]]
        cluster_embeddings = [embeddings[i] for i in range(len(embeddings)) if cluster_mask[i]]

        logger.info(f"\n[{cluster_id + 1}/{n_clusters}] Creating domain with {len(cluster_hang_ids)} nodes...")

        # AgentManager._create_new_domain() 호출
        # 이 메서드가 자동으로:
        # 1. DomainInfo 생성
        # 2. LLM으로 도메인 이름 생성
        # 3. _sync_domain_to_neo4j() 호출
        # 4. _sync_domain_assignments_neo4j() 호출
        domain = manager._create_new_domain(cluster_hang_ids, cluster_embeddings)

        logger.info(f"  Domain created: '{domain.domain_name}' ({domain.domain_id})")
        logger.info(f"  Agent slug: {domain.agent_slug}")
        logger.info(f"  Node count: {domain.size()}")

    logger.info(f"\nAll {n_clusters} domains created successfully!")

    return manager


def verify_neo4j_domains():
    """
    Neo4j에 도메인이 정상적으로 생성되었는지 확인
    """
    logger.info("\nVerifying Neo4j domains...")

    neo4j = get_neo4j_service()

    # Domain 개수 확인
    domain_count_query = "MATCH (d:Domain) RETURN count(d) AS count"
    result = neo4j.execute_query(domain_count_query, {})
    domain_count = result[0]['count'] if result else 0

    logger.info(f"  Total Domain nodes: {domain_count}")

    # 각 도메인 정보 출력
    domain_info_query = """
    MATCH (d:Domain)
    OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
    RETURN d.domain_name AS name,
           d.node_count AS expected,
           count(h) AS actual
    ORDER BY d.node_count DESC
    """

    results = neo4j.execute_query(domain_info_query, {})

    logger.info("\n  Domain details:")
    for record in results:
        match = "[OK]" if record['expected'] == record['actual'] else "[ERROR]"
        logger.info(f"    {match} {record['name']}: {record['actual']}/{record['expected']} nodes")

    # Coverage 확인
    coverage_query = """
    MATCH (h_total:HANG)
    WITH count(h_total) AS total
    MATCH (h_assigned:HANG)-[:BELONGS_TO_DOMAIN]->(:Domain)
    RETURN total, count(h_assigned) AS assigned,
           (count(h_assigned) * 100.0 / total) AS coverage
    """

    result = neo4j.execute_query(coverage_query, {})
    if result:
        data = result[0]
        logger.info(f"\n  Coverage: {data['assigned']}/{data['total']} ({data['coverage']:.1f}%)")

    return domain_count > 0


def main():
    """메인 실행 함수"""
    print("\n" + "="*70)
    print("  Domain Initialization Script")
    print("="*70)

    try:
        # Step 1: 임베딩 로드
        print("\n[Step 1/4] Loading HANG embeddings from Neo4j...")
        hang_ids, embeddings = load_all_hang_embeddings()

        if len(hang_ids) == 0:
            print("\n[ERROR] No HANG nodes found with embeddings!")
            print("Please run 'law/scripts/add_embeddings.py' first.")
            return False

        # Step 2: 클러스터링
        print("\n[Step 2/4] Clustering nodes into domains...")
        n_clusters = 5  # 5개 도메인 생성
        labels = cluster_hangs(embeddings, n_clusters)

        # Step 3: 도메인 생성
        print("\n[Step 3/4] Creating domains via AgentManager...")
        manager = create_domains_via_agent_manager(
            hang_ids, embeddings, labels, n_clusters
        )

        # Step 4: 검증
        print("\n[Step 4/4] Verifying Neo4j domains...")
        success = verify_neo4j_domains()

        # 완료 메시지
        print("\n" + "="*70)
        if success:
            print("[SUCCESS] Domain initialization complete!")
            print("="*70)

            print("\nNext steps:")
            print("1. Open Neo4j Browser: http://localhost:7474")
            print("2. Run visualization query:")
            print("   MATCH (d:Domain)")
            print("   OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)")
            print("   RETURN d, collect(h)[..10] AS sample")
            print("\n3. Check domain statistics:")
            print("   MATCH (d:Domain)")
            print("   RETURN d.domain_name, d.node_count")
            print("   ORDER BY d.node_count DESC")
        else:
            print("[WARNING] Domain creation completed but verification failed")
            print("="*70)

        print(f"\nTotal domains in memory: {len(manager.domains)}")
        print(f"Total HANG nodes assigned: {len(manager.node_to_domain)}")

        return success

    except Exception as e:
        print("\n" + "="*70)
        print(f"[ERROR] Initialization failed: {e}")
        print("="*70)
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
