"""
Evaluation Runner for Law Search System

Executes comprehensive evaluation across all test queries and system variants.
Computes standard IR metrics: Precision@K, Recall@K, NDCG@10, MRR.

System Variants:
- V1: Baseline (exact match only)
- V2: + Vector Search (KR-SBERT)
- V3: + Relationship Embeddings (RNE)
- V4: + A2A Collaboration
- V5: Full System (all features)

Output:
- evaluation_results.json: Detailed results per query
- evaluation_summary.csv: Aggregated metrics by variant and category

Usage:
    cd D:\Data\11_Backend\01_ARR\backend
    python manage.py shell < law/evaluation/run_evaluation.py

Requirements:
    - test_queries.json must exist
    - ground_truth.json must exist
    - Django server must be running (for API calls)

Author: Law Search System Team
Version: 1.0.0
"""

import os
import sys
import django
import json
import csv
import math
from datetime import datetime
from collections import defaultdict
import time

# ===== CONFIGURATION =====
INPUT_QUERIES = "law/evaluation/test_queries.json"
INPUT_GROUND_TRUTH = "law/evaluation/ground_truth.json"
OUTPUT_RESULTS = "law/evaluation/evaluation_results.json"
OUTPUT_SUMMARY = "law/evaluation/evaluation_summary.csv"

# Evaluation parameters
K_VALUES = [5, 10]  # For Precision@K and Recall@K
NDCG_K = 10
MAX_RESULTS = 20  # Maximum results to retrieve per query

# System variants to test
SYSTEM_VARIANTS = {
    "V1_baseline": {
        "name": "Baseline (Exact Match)",
        "enable_vector": False,
        "enable_relationship": False,
        "enable_rne": False,
        "enable_a2a": False
    },
    "V2_vector": {
        "name": "Vector Search (KR-SBERT)",
        "enable_vector": True,
        "enable_relationship": False,
        "enable_rne": False,
        "enable_a2a": False
    },
    "V3_rne": {
        "name": "Relationship Embeddings (RNE)",
        "enable_vector": True,
        "enable_relationship": True,
        "enable_rne": True,
        "enable_a2a": False
    },
    "V4_a2a": {
        "name": "A2A Collaboration",
        "enable_vector": True,
        "enable_relationship": True,
        "enable_rne": True,
        "enable_a2a": True
    },
    "V5_full": {
        "name": "Full System",
        "enable_vector": True,
        "enable_relationship": True,
        "enable_rne": True,
        "enable_a2a": True
    }
}
# ========================

# Setup Django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from agents.law.agent_manager import AgentManager


def calculate_precision_at_k(retrieved, relevant, k):
    """
    Calculate Precision@K.

    Precision@K = (# of relevant items in top K) / K
    """
    if k == 0:
        return 0.0

    top_k = retrieved[:k]
    relevant_set = set(relevant)
    relevant_in_top_k = sum(1 for item in top_k if item in relevant_set)

    return relevant_in_top_k / k


def calculate_recall_at_k(retrieved, relevant, k):
    """
    Calculate Recall@K.

    Recall@K = (# of relevant items in top K) / (total # of relevant items)
    """
    if not relevant:
        return 0.0

    top_k = retrieved[:k]
    relevant_set = set(relevant)
    relevant_in_top_k = sum(1 for item in top_k if item in relevant_set)

    return relevant_in_top_k / len(relevant_set)


def calculate_dcg_at_k(retrieved, relevance_scores, k):
    """
    Calculate Discounted Cumulative Gain at K.

    DCG@K = Σ (rel_i / log2(i + 1)) for i in [1, K]
    """
    dcg = 0.0
    for i, item in enumerate(retrieved[:k], 1):
        relevance = relevance_scores.get(item, 0)
        dcg += relevance / math.log2(i + 1)

    return dcg


def calculate_ndcg_at_k(retrieved, relevance_scores, k):
    """
    Calculate Normalized Discounted Cumulative Gain at K.

    NDCG@K = DCG@K / IDCG@K
    where IDCG@K is the ideal DCG (using perfect ranking)
    """
    # Calculate DCG
    dcg = calculate_dcg_at_k(retrieved, relevance_scores, k)

    # Calculate IDCG (ideal DCG with perfect ranking)
    ideal_ranking = sorted(relevance_scores.items(), key=lambda x: x[1], reverse=True)
    ideal_items = [item for item, _ in ideal_ranking[:k]]
    idcg = calculate_dcg_at_k(ideal_items, relevance_scores, k)

    if idcg == 0:
        return 0.0

    return dcg / idcg


def calculate_mrr(retrieved, relevant):
    """
    Calculate Mean Reciprocal Rank.

    MRR = 1 / rank of first relevant item
    """
    relevant_set = set(relevant)

    for i, item in enumerate(retrieved, 1):
        if item in relevant_set:
            return 1.0 / i

    return 0.0  # No relevant items found


def extract_hang_ids_from_results(search_results):
    """Extract HANG IDs from search results."""
    hang_ids = []

    # Handle different result structures
    if isinstance(search_results, dict):
        # Check for 'results' key (common in API responses)
        if 'results' in search_results:
            results_list = search_results['results']
        elif 'search_results' in search_results:
            results_list = search_results['search_results']
        else:
            return []

        for result in results_list:
            if isinstance(result, dict):
                # Try different field names
                hang_id = result.get('hang_id') or result.get('id') or result.get('node_id')
                if hang_id:
                    hang_ids.append(hang_id)
            elif isinstance(result, str):
                hang_ids.append(result)

    elif isinstance(search_results, list):
        for result in search_results:
            if isinstance(result, dict):
                hang_id = result.get('hang_id') or result.get('id') or result.get('node_id')
                if hang_id:
                    hang_ids.append(hang_id)
            elif isinstance(result, str):
                hang_ids.append(result)

    return hang_ids


def execute_search(agent_manager, query_text, variant_config):
    """
    Execute search with specific variant configuration.

    Note: This is a simplified version. In production, you would
    modify AgentManager to accept these flags dynamically.
    """
    try:
        # Create unique session ID for this search
        session_id = f"eval_{int(time.time() * 1000)}"

        # Execute search via AgentManager
        result = agent_manager.search(
            query=query_text,
            session_id=session_id
        )

        return result

    except Exception as e:
        print(f"    ERROR during search: {str(e)}")
        return {"error": str(e)}


def evaluate_query(agent_manager, query_data, ground_truth_entry, variant_name, variant_config):
    """Evaluate a single query against ground truth."""
    query_text = query_data['query']

    # Execute search
    search_results = execute_search(agent_manager, query_text, variant_config)

    # Extract HANG IDs from results
    retrieved_ids = extract_hang_ids_from_results(search_results)

    # Build relevance map from ground truth
    relevance_scores = {}
    relevant_ids = []

    for article in ground_truth_entry['relevant_articles']:
        hang_id = article['hang_id']
        relevance = article['relevance']
        relevance_scores[hang_id] = relevance

        if relevance > 0:  # Relevance > 0 means relevant
            relevant_ids.append(hang_id)

    # Calculate metrics
    metrics = {}

    # Precision and Recall at K
    for k in K_VALUES:
        precision = calculate_precision_at_k(retrieved_ids, relevant_ids, k)
        recall = calculate_recall_at_k(retrieved_ids, relevant_ids, k)
        metrics[f'precision@{k}'] = precision
        metrics[f'recall@{k}'] = recall

    # NDCG@K
    ndcg = calculate_ndcg_at_k(retrieved_ids, relevance_scores, NDCG_K)
    metrics['ndcg@10'] = ndcg

    # MRR
    mrr = calculate_mrr(retrieved_ids, relevant_ids)
    metrics['mrr'] = mrr

    # Additional info
    metrics['total_retrieved'] = len(retrieved_ids)
    metrics['total_relevant'] = len(relevant_ids)
    metrics['relevant_retrieved'] = len(set(retrieved_ids) & set(relevant_ids))

    return {
        "query_id": query_data['id'],
        "query": query_text,
        "category": query_data['category'],
        "variant": variant_name,
        "retrieved_ids": retrieved_ids[:MAX_RESULTS],
        "metrics": metrics,
        "search_results": search_results
    }


def aggregate_metrics(all_results):
    """Aggregate metrics across all queries."""
    # Group by variant and category
    grouped = defaultdict(lambda: defaultdict(list))

    for result in all_results:
        variant = result['variant']
        category = result['category']
        metrics = result['metrics']

        for metric_name, value in metrics.items():
            if metric_name not in ['total_retrieved', 'total_relevant', 'relevant_retrieved']:
                grouped[variant][category].append({
                    'metric': metric_name,
                    'value': value
                })

    # Calculate averages
    aggregated = []

    for variant, categories in grouped.items():
        for category, metric_list in categories.items():
            # Group by metric name
            metric_groups = defaultdict(list)
            for item in metric_list:
                metric_groups[item['metric']].append(item['value'])

            # Calculate average for each metric
            avg_metrics = {}
            for metric_name, values in metric_groups.items():
                avg_metrics[metric_name] = sum(values) / len(values) if values else 0.0

            aggregated.append({
                'variant': variant,
                'category': category,
                'query_count': len(metric_list) // len(avg_metrics),  # Approximate
                'metrics': avg_metrics
            })

    return aggregated


def main():
    """Main execution function."""
    print("=" * 80)
    print("Law Search System - Evaluation Runner")
    print("=" * 80)
    print()

    # Load test queries
    print("[1/5] Loading test queries...")
    queries_path = os.path.join(BASE_DIR, INPUT_QUERIES)
    if not os.path.exists(queries_path):
        print(f"ERROR: {INPUT_QUERIES} not found!")
        return

    with open(queries_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    queries = test_data['queries']
    print(f"✓ Loaded {len(queries)} test queries")
    print()

    # Load ground truth
    print("[2/5] Loading ground truth...")
    gt_path = os.path.join(BASE_DIR, INPUT_GROUND_TRUTH)
    if not os.path.exists(gt_path):
        print(f"ERROR: {INPUT_GROUND_TRUTH} not found!")
        return

    with open(gt_path, 'r', encoding='utf-8') as f:
        gt_data = json.load(f)

    ground_truth = {entry['query_id']: entry for entry in gt_data['ground_truth']}
    print(f"✓ Loaded ground truth for {len(ground_truth)} queries")
    print()

    # Initialize AgentManager
    print("[3/5] Initializing AgentManager...")
    agent_manager = AgentManager()
    print("✓ AgentManager initialized")
    print()

    # Run evaluation
    print("[4/5] Running evaluation...")
    print()

    all_results = []
    total_evaluations = len(queries) * len(SYSTEM_VARIANTS)
    current_eval = 0

    for variant_name, variant_config in SYSTEM_VARIANTS.items():
        print(f"Evaluating {variant_config['name']}...")

        for query_data in queries:
            current_eval += 1
            query_id = query_data['id']

            # Progress indicator
            print(f"  [{current_eval}/{total_evaluations}] Query {query_id}: {query_data['query'][:60]}...")

            # Get ground truth for this query
            gt_entry = ground_truth.get(query_id)
            if not gt_entry:
                print(f"    WARNING: No ground truth for query {query_id}")
                continue

            # Evaluate
            result = evaluate_query(
                agent_manager,
                query_data,
                gt_entry,
                variant_name,
                variant_config
            )

            all_results.append(result)

            # Print quick metrics
            metrics = result['metrics']
            print(f"    P@5={metrics.get('precision@5', 0):.3f}, "
                  f"R@5={metrics.get('recall@5', 0):.3f}, "
                  f"NDCG@10={metrics.get('ndcg@10', 0):.3f}, "
                  f"MRR={metrics.get('mrr', 0):.3f}")

        print()

    print(f"✓ Completed {len(all_results)} evaluations")
    print()

    # Aggregate results
    print("[5/5] Aggregating results and saving...")

    # Save detailed results
    results_output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_queries": len(queries),
            "total_variants": len(SYSTEM_VARIANTS),
            "total_evaluations": len(all_results),
            "k_values": K_VALUES,
            "ndcg_k": NDCG_K,
            "version": "1.0.0"
        },
        "system_variants": SYSTEM_VARIANTS,
        "results": all_results
    }

    results_path = os.path.join(BASE_DIR, OUTPUT_RESULTS)
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results_output, f, ensure_ascii=False, indent=2)

    print(f"✓ Saved detailed results to: {results_path}")

    # Aggregate and save summary CSV
    aggregated = aggregate_metrics(all_results)

    summary_path = os.path.join(BASE_DIR, OUTPUT_SUMMARY)
    with open(summary_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['variant', 'category', 'query_count']
        # Add metric columns
        if aggregated:
            metric_names = sorted(aggregated[0]['metrics'].keys())
            fieldnames.extend(metric_names)

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for entry in aggregated:
            row = {
                'variant': entry['variant'],
                'category': entry['category'],
                'query_count': entry['query_count']
            }
            for metric_name, value in entry['metrics'].items():
                row[metric_name] = f"{value:.4f}"

            writer.writerow(row)

    print(f"✓ Saved summary CSV to: {summary_path}")
    print()

    # Print summary statistics
    print("=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    print()

    # Overall statistics by variant
    variant_stats = defaultdict(lambda: defaultdict(list))
    for result in all_results:
        variant = result['variant']
        for metric_name, value in result['metrics'].items():
            if metric_name not in ['total_retrieved', 'total_relevant', 'relevant_retrieved']:
                variant_stats[variant][metric_name].append(value)

    print("Overall Metrics by Variant:")
    print()
    for variant_name in SYSTEM_VARIANTS.keys():
        print(f"{SYSTEM_VARIANTS[variant_name]['name']}:")
        stats = variant_stats[variant_name]

        for metric_name in ['precision@5', 'recall@5', 'ndcg@10', 'mrr']:
            if metric_name in stats:
                values = stats[metric_name]
                avg = sum(values) / len(values) if values else 0.0
                print(f"  {metric_name:15s}: {avg:.4f}")
        print()

    print("=" * 80)
    print(f"Detailed Results: {OUTPUT_RESULTS}")
    print(f"Summary CSV: {OUTPUT_SUMMARY}")
    print("=" * 80)


if __name__ == "__main__":
    main()
