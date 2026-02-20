"""
Test Query Generator for Law Search System

Generates 50 diverse test queries across 4 categories by extracting real data from Neo4j.

Categories:
- Category A (Article Numbers): Direct article references like "17조", "21조"
- Category B (Keywords): Domain-specific terms like "용도지역", "도시계획"
- Category C (Complex Questions): Natural language questions
- Category D (Cross-Law Queries): Queries spanning 법률/시행령/시행규칙

Output: test_queries.json in the evaluation directory

Usage:
    cd D:\Data\11_Backend\01_ARR\backend
    python manage.py shell < law/evaluation/generate_test_queries.py

Author: Law Search System Team
Version: 1.0.0
"""

import os
import sys
import django
import json
import random
from datetime import datetime
from collections import defaultdict

# ===== CONFIGURATION =====
OUTPUT_FILE = "law/evaluation/test_queries.json"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Dmstn147!!"

# Query distribution
CATEGORY_A_COUNT = 15  # Article numbers
CATEGORY_B_COUNT = 15  # Keywords
CATEGORY_C_COUNT = 10  # Complex questions
CATEGORY_D_COUNT = 10  # Cross-law queries
# ========================

# Setup Django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


def extract_article_numbers(neo4j_service):
    """Extract unique article numbers from Neo4j HANG nodes."""
    query = """
    MATCH (h:HANG)
    WHERE h.article_number IS NOT NULL
    RETURN DISTINCT h.article_number as article_number,
           h.law_name as law_name,
           h.content as content
    ORDER BY h.article_number
    LIMIT 200
    """
    results = neo4j_service.execute_query(query)
    articles = []
    for record in results:
        articles.append({
            'number': record['article_number'],
            'law_name': record['law_name'],
            'content': record['content'][:100] if record['content'] else ""
        })
    return articles


def extract_keywords(neo4j_service):
    """Extract common keywords from HANG node contents."""
    query = """
    MATCH (h:HANG)
    WHERE h.content IS NOT NULL
    RETURN h.content as content
    LIMIT 500
    """
    results = neo4j_service.execute_query(query)

    # Common legal keywords to look for
    common_keywords = [
        "용도지역", "도시계획", "건축제한", "토지이용", "개발행위",
        "지구단위계획", "도시관리계획", "기반시설", "정비구역", "특별계획구역",
        "국토계획", "광역도시계획", "녹지지역", "주거지역", "상업지역",
        "공업지역", "자연환경보전지역", "도시자연공원구역", "시가화조정구역",
        "수립권자", "승인권자", "주민의견", "환경성검토", "재해취약성분석"
    ]

    # Find keywords that actually appear in content
    keyword_counts = defaultdict(int)
    for record in results:
        content = record['content']
        for keyword in common_keywords:
            if keyword in content:
                keyword_counts[keyword] += 1

    # Sort by frequency
    sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, count in sorted_keywords]


def extract_law_metadata(neo4j_service):
    """Extract law names and types for cross-law queries."""
    query = """
    MATCH (l:LAW)
    RETURN DISTINCT l.law_name as law_name, l.law_type as law_type
    ORDER BY l.law_name
    """
    results = neo4j_service.execute_query(query)
    laws = []
    for record in results:
        laws.append({
            'name': record['law_name'],
            'type': record['law_type']
        })
    return laws


def generate_category_a_queries(articles):
    """Generate article number queries (Category A)."""
    queries = []
    selected = random.sample(articles, min(CATEGORY_A_COUNT, len(articles)))

    for idx, article in enumerate(selected, 1):
        queries.append({
            "id": idx,
            "category": "article_number",
            "query": article['number'],
            "description": f"{article['law_name']} {article['number']} 관련 조문 검색",
            "metadata": {
                "law_name": article['law_name'],
                "article_number": article['number']
            }
        })

    return queries


def generate_category_b_queries(keywords):
    """Generate keyword-based queries (Category B)."""
    queries = []
    selected = keywords[:CATEGORY_B_COUNT]

    keyword_templates = [
        "{keyword}에 대해 알려주세요",
        "{keyword}란 무엇인가요",
        "{keyword} 관련 법령",
        "{keyword}의 정의",
        "{keyword}"
    ]

    for idx, keyword in enumerate(selected, CATEGORY_A_COUNT + 1):
        template = random.choice(keyword_templates)
        queries.append({
            "id": idx,
            "category": "keyword",
            "query": template.format(keyword=keyword),
            "description": f"{keyword} 관련 법령 검색",
            "metadata": {
                "keyword": keyword,
                "template": template
            }
        })

    return queries


def generate_category_c_queries(keywords, articles):
    """Generate complex question queries (Category C)."""
    queries = []

    complex_templates = [
        "{keyword} 변경 절차는?",
        "{keyword} 수립 기준에 대해 설명해주세요",
        "{keyword}의 지정 요건은 무엇인가요?",
        "{keyword} 해제 절차를 알려주세요",
        "{keyword} 관련 주민의견 청취 절차는?",
        "{article_num}에서 규정하는 {keyword}의 내용은?",
        "{keyword}과 관련된 환경성 검토 기준은?",
        "{keyword} 지정 시 고려사항은?",
        "{keyword}에 대한 이의신청 절차는?",
        "{keyword} 관련 권한은 누가 가지나요?"
    ]

    start_id = CATEGORY_A_COUNT + CATEGORY_B_COUNT + 1

    for idx in range(CATEGORY_C_COUNT):
        template = complex_templates[idx]

        if "{article_num}" in template and "{keyword}" in template:
            article = random.choice(articles)
            keyword = random.choice(keywords[:10])
            query_text = template.format(article_num=article['number'], keyword=keyword)
            metadata = {
                "article_number": article['number'],
                "keyword": keyword,
                "template": template
            }
        else:
            keyword = random.choice(keywords[:10])
            query_text = template.format(keyword=keyword)
            metadata = {
                "keyword": keyword,
                "template": template
            }

        queries.append({
            "id": start_id + idx,
            "category": "complex_question",
            "query": query_text,
            "description": f"복합 질의: {query_text}",
            "metadata": metadata
        })

    return queries


def generate_category_d_queries(laws, articles):
    """Generate cross-law queries (Category D) spanning 법률/시행령/시행규칙."""
    queries = []

    # Group laws by base name
    law_groups = defaultdict(list)
    for law in laws:
        base_name = law['name'].replace('시행령', '').replace('시행규칙', '').strip()
        law_groups[base_name].append(law)

    cross_law_templates = [
        "{law_name} 시행령 내용은?",
        "{law_name} 시행규칙 알려주세요",
        "{law_name}과 시행령의 관계는?",
        "{article_num}의 시행령 규정은?",
        "{law_name} 법률과 시행령 비교",
        "{law_name} 시행규칙의 세부 기준",
        "{article_num} 관련 시행령 조항",
        "{law_name}의 하위 법령은?",
        "{law_name} 법체계 설명해주세요",
        "{article_num}을 구체화하는 시행령은?"
    ]

    start_id = CATEGORY_A_COUNT + CATEGORY_B_COUNT + CATEGORY_C_COUNT + 1

    for idx in range(CATEGORY_D_COUNT):
        template = cross_law_templates[idx]

        if "{article_num}" in template:
            article = random.choice(articles)
            query_text = template.format(article_num=article['number'])
            metadata = {
                "article_number": article['number'],
                "template": template,
                "cross_law": True
            }
        else:
            law = random.choice(laws)
            base_name = law['name'].replace('시행령', '').replace('시행규칙', '').strip()
            query_text = template.format(law_name=base_name)
            metadata = {
                "law_name": base_name,
                "template": template,
                "cross_law": True
            }

        queries.append({
            "id": start_id + idx,
            "category": "cross_law",
            "query": query_text,
            "description": f"법령 간 관계 질의: {query_text}",
            "metadata": metadata
        })

    return queries


def main():
    """Main execution function."""
    print("=" * 80)
    print("Law Search System - Test Query Generator")
    print("=" * 80)
    print()

    # Connect to Neo4j
    print("[1/6] Connecting to Neo4j...")
    neo4j_service = Neo4jService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    print("✓ Connected to Neo4j")
    print()

    # Extract data from Neo4j
    print("[2/6] Extracting article numbers from HANG nodes...")
    articles = extract_article_numbers(neo4j_service)
    print(f"✓ Extracted {len(articles)} unique articles")
    print()

    print("[3/6] Extracting keywords from content...")
    keywords = extract_keywords(neo4j_service)
    print(f"✓ Extracted {len(keywords)} keywords")
    print()

    print("[4/6] Extracting law metadata...")
    laws = extract_law_metadata(neo4j_service)
    print(f"✓ Extracted {len(laws)} laws")
    print()

    # Generate queries
    print("[5/6] Generating test queries...")
    all_queries = []

    category_a = generate_category_a_queries(articles)
    print(f"  ✓ Category A (Article Numbers): {len(category_a)} queries")
    all_queries.extend(category_a)

    category_b = generate_category_b_queries(keywords)
    print(f"  ✓ Category B (Keywords): {len(category_b)} queries")
    all_queries.extend(category_b)

    category_c = generate_category_c_queries(keywords, articles)
    print(f"  ✓ Category C (Complex Questions): {len(category_c)} queries")
    all_queries.extend(category_c)

    category_d = generate_category_d_queries(laws, articles)
    print(f"  ✓ Category D (Cross-Law): {len(category_d)} queries")
    all_queries.extend(category_d)

    print(f"\nTotal queries generated: {len(all_queries)}")
    print()

    # Save to JSON
    print("[6/6] Saving to file...")
    output_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_queries": len(all_queries),
            "categories": {
                "article_number": CATEGORY_A_COUNT,
                "keyword": CATEGORY_B_COUNT,
                "complex_question": CATEGORY_C_COUNT,
                "cross_law": CATEGORY_D_COUNT
            },
            "source": "Neo4j Law Database",
            "version": "1.0.0"
        },
        "queries": all_queries
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
    print(f"Total Queries: {len(all_queries)}")
    print(f"\nCategory Breakdown:")
    print(f"  A. Article Numbers:    {CATEGORY_A_COUNT:2d} queries")
    print(f"  B. Keywords:           {CATEGORY_B_COUNT:2d} queries")
    print(f"  C. Complex Questions:  {CATEGORY_C_COUNT:2d} queries")
    print(f"  D. Cross-Law:          {CATEGORY_D_COUNT:2d} queries")
    print()
    print(f"Output File: {OUTPUT_FILE}")
    print()
    print("Next Step: Run generate_ground_truth.py to create ground truth judgments")
    print("=" * 80)

    # Close Neo4j connection
    neo4j_service.close()


if __name__ == "__main__":
    main()
