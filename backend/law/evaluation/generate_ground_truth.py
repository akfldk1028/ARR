"""
Ground Truth Generator for Law Search System Evaluation

Automatically generates ground truth relevance judgments for test queries by
analyzing the Neo4j graph structure and relationships.

Relevance Scoring:
- Score 3 (Exact Match): The queried article itself
- Score 2 (Highly Relevant): Child HO nodes, parent JO, related 시행령/시행규칙
- Score 1 (Somewhat Relevant): Related articles via graph relationships
- Score 0 (Not Relevant): Unrelated articles

Output: ground_truth.json in the evaluation directory

Usage:
    cd D:\Data\11_Backend\01_ARR\backend
    python manage.py shell < law/evaluation/generate_ground_truth.py

Requirements:
    - test_queries.json must exist (run generate_test_queries.py first)

Author: Law Search System Team
Version: 1.0.0
"""

import os
import sys
import django
import json
from datetime import datetime
from collections import defaultdict

# ===== CONFIGURATION =====
INPUT_FILE = "law/evaluation/test_queries.json"
OUTPUT_FILE = "law/evaluation/ground_truth.json"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Dmstn147!!"

# Relevance scoring thresholds
EXACT_MATCH_SCORE = 3
HIGHLY_RELEVANT_SCORE = 2
SOMEWHAT_RELEVANT_SCORE = 1
NOT_RELEVANT_SCORE = 0

# Maximum results per query
MAX_RESULTS_PER_QUERY = 50
# ========================

# Setup Django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


def find_exact_match_by_article_number(neo4j_service, article_number, law_name=None):
    """Find HANG nodes that exactly match the article number."""
    if law_name:
        query = """
        MATCH (h:HANG)
        WHERE h.article_number = $article_number
          AND h.law_name CONTAINS $law_name
        RETURN h.hang_id as hang_id,
               h.article_number as article_number,
               h.law_name as law_name,
               h.content as content
        LIMIT 10
        """
        params = {"article_number": article_number, "law_name": law_name}
    else:
        query = """
        MATCH (h:HANG)
        WHERE h.article_number = $article_number
        RETURN h.hang_id as hang_id,
               h.article_number as article_number,
               h.law_name as law_name,
               h.content as content
        LIMIT 10
        """
        params = {"article_number": article_number}

    results = neo4j_service.execute_query(query, params)
    return [dict(record) for record in results]


def find_related_nodes(neo4j_service, hang_id):
    """Find related nodes via graph relationships."""
    query = """
    MATCH (h:HANG {hang_id: $hang_id})

    // Get child HO nodes
    OPTIONAL MATCH (h)-[:HAS_HO]->(ho:HO)

    // Get parent JO node
    OPTIONAL MATCH (jo:JO)-[:HAS_HANG]->(h)

    // Get sibling HANG nodes (same JO)
    OPTIONAL MATCH (jo)-[:HAS_HANG]->(sibling:HANG)
    WHERE sibling.hang_id <> $hang_id

    // Get referenced HANGs
    OPTIONAL MATCH (h)-[:REFERENCES]->(ref:HANG)

    // Get referencing HANGs
    OPTIONAL MATCH (referrer:HANG)-[:REFERENCES]->(h)

    RETURN
        collect(DISTINCT ho.ho_id) as child_hos,
        jo.jo_id as parent_jo,
        collect(DISTINCT sibling.hang_id) as sibling_hangs,
        collect(DISTINCT ref.hang_id) as referenced_hangs,
        collect(DISTINCT referrer.hang_id) as referencing_hangs
    """
    result = neo4j_service.execute_query(query, {"hang_id": hang_id})
    if result:
        return dict(result[0])
    return {}


def find_related_laws(neo4j_service, law_name):
    """Find related 시행령/시행규칙 for a given law."""
    # Extract base law name
    base_name = law_name.replace('시행령', '').replace('시행규칙', '').strip()

    query = """
    MATCH (l:LAW)
    WHERE l.law_name CONTAINS $base_name
    RETURN l.law_name as law_name,
           l.law_type as law_type
    """
    results = neo4j_service.execute_query(query, {"base_name": base_name})
    return [dict(record) for record in results]


def find_hangs_by_keyword(neo4j_service, keyword, limit=20):
    """Find HANG nodes containing the keyword."""
    query = """
    MATCH (h:HANG)
    WHERE h.content CONTAINS $keyword
    RETURN h.hang_id as hang_id,
           h.article_number as article_number,
           h.law_name as law_name,
           h.content as content
    LIMIT $limit
    """
    results = neo4j_service.execute_query(query, {"keyword": keyword, "limit": limit})
    return [dict(record) for record in results]


def find_hangs_by_law_type(neo4j_service, law_name, law_type):
    """Find HANG nodes from a specific law type (법률/시행령/시행규칙)."""
    query = """
    MATCH (l:LAW {law_name: $law_name, law_type: $law_type})-[:HAS_JO]->(j:JO)-[:HAS_HANG]->(h:HANG)
    RETURN h.hang_id as hang_id,
           h.article_number as article_number,
           h.law_name as law_name,
           h.content as content
    LIMIT 20
    """
    results = neo4j_service.execute_query(query, {"law_name": law_name, "law_type": law_type})
    return [dict(record) for record in results]


def generate_ground_truth_for_article_query(neo4j_service, query_data):
    """Generate ground truth for article number queries (Category A)."""
    article_number = query_data['metadata'].get('article_number', query_data['query'])
    law_name = query_data['metadata'].get('law_name')

    relevant_articles = []

    # Find exact matches (Score 3)
    exact_matches = find_exact_match_by_article_number(neo4j_service, article_number, law_name)

    for match in exact_matches:
        hang_id = match['hang_id']
        relevant_articles.append({
            "hang_id": hang_id,
            "article_number": match['article_number'],
            "law_name": match['law_name'],
            "relevance": EXACT_MATCH_SCORE,
            "reason": "exact_match",
            "content_preview": match['content'][:200] if match['content'] else ""
        })

        # Find related nodes (Score 2 and 1)
        related = find_related_nodes(neo4j_service, hang_id)

        # Parent JO is highly relevant
        if related.get('parent_jo'):
            relevant_articles.append({
                "hang_id": related['parent_jo'],
                "relevance": HIGHLY_RELEVANT_SCORE,
                "reason": "parent_jo"
            })

        # Child HO nodes are highly relevant
        for ho_id in related.get('child_hos', [])[:5]:
            relevant_articles.append({
                "hang_id": ho_id,
                "relevance": HIGHLY_RELEVANT_SCORE,
                "reason": "child_ho"
            })

        # Referenced and referencing HANGs are somewhat relevant
        for ref_hang in related.get('referenced_hangs', [])[:3]:
            relevant_articles.append({
                "hang_id": ref_hang,
                "relevance": SOMEWHAT_RELEVANT_SCORE,
                "reason": "references"
            })

        for referrer_hang in related.get('referencing_hangs', [])[:3]:
            relevant_articles.append({
                "hang_id": referrer_hang,
                "relevance": SOMEWHAT_RELEVANT_SCORE,
                "reason": "referenced_by"
            })

    return relevant_articles


def generate_ground_truth_for_keyword_query(neo4j_service, query_data):
    """Generate ground truth for keyword queries (Category B)."""
    keyword = query_data['metadata'].get('keyword', '')

    relevant_articles = []

    # Find HANGs containing the keyword
    matches = find_hangs_by_keyword(neo4j_service, keyword, limit=30)

    for idx, match in enumerate(matches):
        # First 5 are highly relevant, rest are somewhat relevant
        if idx < 5:
            relevance = HIGHLY_RELEVANT_SCORE
            reason = "keyword_primary_match"
        else:
            relevance = SOMEWHAT_RELEVANT_SCORE
            reason = "keyword_secondary_match"

        relevant_articles.append({
            "hang_id": match['hang_id'],
            "article_number": match['article_number'],
            "law_name": match['law_name'],
            "relevance": relevance,
            "reason": reason,
            "content_preview": match['content'][:200] if match['content'] else ""
        })

    return relevant_articles


def generate_ground_truth_for_complex_query(neo4j_service, query_data):
    """Generate ground truth for complex question queries (Category C)."""
    keyword = query_data['metadata'].get('keyword', '')
    article_number = query_data['metadata'].get('article_number')

    relevant_articles = []

    # If article number is mentioned, find it first
    if article_number:
        exact_matches = find_exact_match_by_article_number(neo4j_service, article_number)
        for match in exact_matches:
            relevant_articles.append({
                "hang_id": match['hang_id'],
                "article_number": match['article_number'],
                "law_name": match['law_name'],
                "relevance": EXACT_MATCH_SCORE,
                "reason": "article_in_complex_query",
                "content_preview": match['content'][:200] if match['content'] else ""
            })

    # Find keyword matches
    keyword_matches = find_hangs_by_keyword(neo4j_service, keyword, limit=20)
    for idx, match in enumerate(keyword_matches[:10]):
        # Avoid duplicates
        if any(a['hang_id'] == match['hang_id'] for a in relevant_articles):
            continue

        relevance = HIGHLY_RELEVANT_SCORE if idx < 3 else SOMEWHAT_RELEVANT_SCORE
        relevant_articles.append({
            "hang_id": match['hang_id'],
            "article_number": match['article_number'],
            "law_name": match['law_name'],
            "relevance": relevance,
            "reason": "keyword_in_complex_query",
            "content_preview": match['content'][:200] if match['content'] else ""
        })

    return relevant_articles


def generate_ground_truth_for_cross_law_query(neo4j_service, query_data):
    """Generate ground truth for cross-law queries (Category D)."""
    law_name = query_data['metadata'].get('law_name', '')
    article_number = query_data['metadata'].get('article_number')

    relevant_articles = []

    # Find related laws (법률, 시행령, 시행규칙)
    related_laws = find_related_laws(neo4j_service, law_name)

    # For each related law type, get HANGs
    for law in related_laws:
        law_type = law['law_type']
        law_full_name = law['law_name']

        hangs = find_hangs_by_law_type(neo4j_service, law_full_name, law_type)

        for idx, hang in enumerate(hangs[:5]):
            # 법률 is exact match, 시행령/시행규칙 are highly relevant
            if law_type == '법률':
                relevance = EXACT_MATCH_SCORE if idx < 2 else HIGHLY_RELEVANT_SCORE
                reason = "base_law"
            elif law_type == '시행령':
                relevance = HIGHLY_RELEVANT_SCORE
                reason = "related_enforcement_decree"
            elif law_type == '시행규칙':
                relevance = HIGHLY_RELEVANT_SCORE
                reason = "related_enforcement_rule"
            else:
                relevance = SOMEWHAT_RELEVANT_SCORE
                reason = "related_law"

            relevant_articles.append({
                "hang_id": hang['hang_id'],
                "article_number": hang['article_number'],
                "law_name": hang['law_name'],
                "law_type": law_type,
                "relevance": relevance,
                "reason": reason,
                "content_preview": hang['content'][:200] if hang['content'] else ""
            })

    # If article number is mentioned, prioritize it
    if article_number:
        exact_matches = find_exact_match_by_article_number(neo4j_service, article_number)
        for match in exact_matches:
            # Add to front of list
            relevant_articles.insert(0, {
                "hang_id": match['hang_id'],
                "article_number": match['article_number'],
                "law_name": match['law_name'],
                "relevance": EXACT_MATCH_SCORE,
                "reason": "article_in_cross_law_query",
                "content_preview": match['content'][:200] if match['content'] else ""
            })

    return relevant_articles


def generate_ground_truth(neo4j_service, queries):
    """Generate ground truth for all queries."""
    ground_truth_data = []

    for idx, query_data in enumerate(queries, 1):
        print(f"  Processing query {idx}/{len(queries)}: {query_data['query'][:50]}...")

        category = query_data['category']

        if category == 'article_number':
            relevant_articles = generate_ground_truth_for_article_query(neo4j_service, query_data)
        elif category == 'keyword':
            relevant_articles = generate_ground_truth_for_keyword_query(neo4j_service, query_data)
        elif category == 'complex_question':
            relevant_articles = generate_ground_truth_for_complex_query(neo4j_service, query_data)
        elif category == 'cross_law':
            relevant_articles = generate_ground_truth_for_cross_law_query(neo4j_service, query_data)
        else:
            relevant_articles = []

        # Remove duplicates and limit results
        seen_hang_ids = set()
        unique_articles = []
        for article in relevant_articles:
            hang_id = article['hang_id']
            if hang_id not in seen_hang_ids:
                seen_hang_ids.add(hang_id)
                unique_articles.append(article)

        # Sort by relevance (descending)
        unique_articles.sort(key=lambda x: x['relevance'], reverse=True)

        # Limit to MAX_RESULTS_PER_QUERY
        unique_articles = unique_articles[:MAX_RESULTS_PER_QUERY]

        ground_truth_entry = {
            "query_id": query_data['id'],
            "category": category,
            "query": query_data['query'],
            "total_relevant": len(unique_articles),
            "relevant_articles": unique_articles
        }

        ground_truth_data.append(ground_truth_entry)

    return ground_truth_data


def main():
    """Main execution function."""
    print("=" * 80)
    print("Law Search System - Ground Truth Generator")
    print("=" * 80)
    print()

    # Load test queries
    print("[1/4] Loading test queries...")
    input_path = os.path.join(BASE_DIR, INPUT_FILE)
    if not os.path.exists(input_path):
        print(f"ERROR: {INPUT_FILE} not found!")
        print("Please run generate_test_queries.py first.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    queries = test_data['queries']
    print(f"✓ Loaded {len(queries)} test queries")
    print()

    # Connect to Neo4j
    print("[2/4] Connecting to Neo4j...")
    neo4j_service = Neo4jService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    print("✓ Connected to Neo4j")
    print()

    # Generate ground truth
    print("[3/4] Generating ground truth relevance judgments...")
    ground_truth = generate_ground_truth(neo4j_service, queries)
    print(f"✓ Generated ground truth for {len(ground_truth)} queries")
    print()

    # Statistics
    total_relevant = sum(entry['total_relevant'] for entry in ground_truth)
    avg_relevant = total_relevant / len(ground_truth) if ground_truth else 0

    print(f"Statistics:")
    print(f"  Total relevant articles: {total_relevant}")
    print(f"  Average per query: {avg_relevant:.2f}")
    print()

    # Save to JSON
    print("[4/4] Saving to file...")
    output_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_queries": len(queries),
            "total_relevant_articles": total_relevant,
            "average_relevant_per_query": round(avg_relevant, 2),
            "relevance_scale": {
                "3": "Exact match",
                "2": "Highly relevant",
                "1": "Somewhat relevant",
                "0": "Not relevant"
            },
            "source": "Neo4j Law Database + Graph Analysis",
            "version": "1.0.0"
        },
        "ground_truth": ground_truth
    }

    output_path = os.path.join(BASE_DIR, OUTPUT_FILE)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"✓ Saved to: {output_path}")
    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Queries: {len(ground_truth)}")
    print(f"Total Relevant Articles: {total_relevant}")
    print(f"Average Relevant per Query: {avg_relevant:.2f}")
    print()

    # Breakdown by category
    category_stats = defaultdict(lambda: {"count": 0, "total_relevant": 0})
    for entry in ground_truth:
        cat = entry['category']
        category_stats[cat]["count"] += 1
        category_stats[cat]["total_relevant"] += entry['total_relevant']

    print("Category Breakdown:")
    for cat, stats in category_stats.items():
        avg = stats["total_relevant"] / stats["count"] if stats["count"] > 0 else 0
        print(f"  {cat:20s}: {stats['count']:2d} queries, "
              f"{stats['total_relevant']:3d} relevant articles, "
              f"avg {avg:.1f}")
    print()
    print(f"Output File: {OUTPUT_FILE}")
    print()
    print("Next Step: Run run_evaluation.py to evaluate system performance")
    print("=" * 80)

    # Close Neo4j connection
    neo4j_service.close()


if __name__ == "__main__":
    main()
