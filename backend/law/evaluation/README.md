# Law Search System Evaluation Framework

Comprehensive evaluation system for the law search platform with automated test query generation, ground truth creation, and performance measurement.

## Overview

This evaluation framework provides:

1. **Automated Test Query Generation** - Extracts real data from Neo4j to create diverse test queries
2. **Ground Truth Creation** - Uses graph analysis to automatically generate relevance judgments
3. **Comprehensive Evaluation** - Measures system performance using standard IR metrics

## Components

### 1. `generate_test_queries.py`

Generates 50 test queries across 4 categories by connecting to Neo4j and extracting actual legal data.

**Categories:**
- **Category A (15 queries)**: Article numbers ("17조", "21조", "42조")
- **Category B (15 queries)**: Keywords ("용도지역", "도시계획", "건축제한")
- **Category C (10 queries)**: Complex questions ("용도지역 변경 절차는?")
- **Category D (10 queries)**: Cross-law queries (법률/시행령/시행규칙)

**Output:** `test_queries.json`

### 2. `generate_ground_truth.py`

Automatically generates ground truth relevance judgments by analyzing Neo4j graph structure.

**Relevance Scoring:**
- **Score 3 (Exact Match)**: The queried article itself
- **Score 2 (Highly Relevant)**: Child HO nodes, parent JO, related 시행령/시행규칙
- **Score 1 (Somewhat Relevant)**: Related articles via graph relationships
- **Score 0 (Not Relevant)**: Unrelated articles

**Output:** `ground_truth.json`

### 3. `run_evaluation.py`

Executes comprehensive evaluation across all queries and system variants.

**System Variants:**
- **V1**: Baseline (exact match only)
- **V2**: Vector Search (KR-SBERT)
- **V3**: Relationship Embeddings (RNE)
- **V4**: A2A Collaboration
- **V5**: Full System (all features)

**Metrics:**
- Precision@K (K=5, 10)
- Recall@K (K=5, 10)
- NDCG@10 (Normalized Discounted Cumulative Gain)
- MRR (Mean Reciprocal Rank)

**Output:**
- `evaluation_results.json` (detailed results)
- `evaluation_summary.csv` (aggregated metrics)

## Usage

### Prerequisites

1. Neo4j database must be running with law data loaded
2. Django server must be configured
3. AgentManager must be accessible

### Step 1: Generate Test Queries

```bash
cd D:\Data\11_Backend\01_ARR\backend
python manage.py shell < law/evaluation/generate_test_queries.py
```

**Output:** `law/evaluation/test_queries.json`

### Step 2: Generate Ground Truth

```bash
python manage.py shell < law/evaluation/generate_ground_truth.py
```

**Output:** `law/evaluation/ground_truth.json`

### Step 3: Run Evaluation

```bash
python manage.py shell < law/evaluation/run_evaluation.py
```

**Output:**
- `law/evaluation/evaluation_results.json`
- `law/evaluation/evaluation_summary.csv`

### Run All Steps

```bash
cd D:\Data\11_Backend\01_ARR\backend
python manage.py shell < law/evaluation/generate_test_queries.py
python manage.py shell < law/evaluation/generate_ground_truth.py
python manage.py shell < law/evaluation/run_evaluation.py
```

## Configuration

Each script has a configuration section at the top:

### `generate_test_queries.py`

```python
OUTPUT_FILE = "law/evaluation/test_queries.json"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Dmstn147!!"

CATEGORY_A_COUNT = 15  # Article numbers
CATEGORY_B_COUNT = 15  # Keywords
CATEGORY_C_COUNT = 10  # Complex questions
CATEGORY_D_COUNT = 10  # Cross-law queries
```

### `generate_ground_truth.py`

```python
INPUT_FILE = "law/evaluation/test_queries.json"
OUTPUT_FILE = "law/evaluation/ground_truth.json"

EXACT_MATCH_SCORE = 3
HIGHLY_RELEVANT_SCORE = 2
SOMEWHAT_RELEVANT_SCORE = 1
NOT_RELEVANT_SCORE = 0

MAX_RESULTS_PER_QUERY = 50
```

### `run_evaluation.py`

```python
INPUT_QUERIES = "law/evaluation/test_queries.json"
INPUT_GROUND_TRUTH = "law/evaluation/ground_truth.json"
OUTPUT_RESULTS = "law/evaluation/evaluation_results.json"
OUTPUT_SUMMARY = "law/evaluation/evaluation_summary.csv"

K_VALUES = [5, 10]
NDCG_K = 10
MAX_RESULTS = 20
```

## Output Files

### `test_queries.json`

```json
{
  "metadata": {
    "generated_at": "2025-11-17T10:00:00",
    "total_queries": 50,
    "categories": {
      "article_number": 15,
      "keyword": 15,
      "complex_question": 10,
      "cross_law": 10
    }
  },
  "queries": [
    {
      "id": 1,
      "category": "article_number",
      "query": "17조",
      "description": "국토계획법 17조 관련 조문 검색",
      "metadata": {
        "law_name": "국토의 계획 및 이용에 관한 법률",
        "article_number": "17조"
      }
    }
  ]
}
```

### `ground_truth.json`

```json
{
  "metadata": {
    "generated_at": "2025-11-17T10:30:00",
    "total_queries": 50,
    "total_relevant_articles": 850,
    "average_relevant_per_query": 17.0
  },
  "ground_truth": [
    {
      "query_id": 1,
      "category": "article_number",
      "query": "17조",
      "total_relevant": 12,
      "relevant_articles": [
        {
          "hang_id": "국토계획법_17조_1항",
          "article_number": "17조",
          "law_name": "국토의 계획 및 이용에 관한 법률",
          "relevance": 3,
          "reason": "exact_match",
          "content_preview": "..."
        }
      ]
    }
  ]
}
```

### `evaluation_results.json`

```json
{
  "metadata": {
    "generated_at": "2025-11-17T11:00:00",
    "total_queries": 50,
    "total_variants": 5,
    "total_evaluations": 250
  },
  "results": [
    {
      "query_id": 1,
      "query": "17조",
      "category": "article_number",
      "variant": "V5_full",
      "retrieved_ids": [...],
      "metrics": {
        "precision@5": 0.8,
        "recall@5": 0.4,
        "precision@10": 0.7,
        "recall@10": 0.7,
        "ndcg@10": 0.85,
        "mrr": 1.0
      }
    }
  ]
}
```

### `evaluation_summary.csv`

```csv
variant,category,query_count,precision@5,recall@5,precision@10,recall@10,ndcg@10,mrr
V5_full,article_number,15,0.8200,0.4500,0.7100,0.6800,0.8300,0.9200
V5_full,keyword,15,0.7500,0.3800,0.6500,0.5900,0.7800,0.8500
...
```

## Metrics Explanation

### Precision@K
Proportion of relevant items in top K results.
```
Precision@K = (# relevant in top K) / K
```

### Recall@K
Proportion of all relevant items found in top K results.
```
Recall@K = (# relevant in top K) / (total # relevant)
```

### NDCG@10
Normalized Discounted Cumulative Gain - considers both relevance and ranking position.
```
NDCG@K = DCG@K / IDCG@K
```

### MRR
Mean Reciprocal Rank - focuses on the rank of the first relevant item.
```
MRR = 1 / (rank of first relevant item)
```

## Error Handling

All scripts include:
- Input validation
- Neo4j connection error handling
- Missing file checks
- Progress indicators
- Detailed error messages

## Extending the Framework

### Adding New Query Categories

Edit `generate_test_queries.py`:

```python
CATEGORY_E_COUNT = 10

def generate_category_e_queries(data):
    # Your implementation
    pass
```

### Adding New Metrics

Edit `run_evaluation.py`:

```python
def calculate_custom_metric(retrieved, relevant):
    # Your implementation
    pass
```

### Adding New System Variants

Edit `run_evaluation.py`:

```python
SYSTEM_VARIANTS["V6_custom"] = {
    "name": "Custom Configuration",
    "enable_vector": True,
    "enable_relationship": True,
    "enable_rne": True,
    "enable_a2a": True,
    "custom_flag": True
}
```

## Troubleshooting

### Neo4j Connection Issues

Verify connection parameters in script configuration:
```python
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Dmstn147!!"
```

### Missing Dependencies

Ensure Django is properly configured:
```bash
cd D:\Data\11_Backend\01_ARR\backend
python manage.py check
```

### Empty Results

Check that:
1. Neo4j database has law data loaded
2. HANG nodes have embeddings
3. AgentManager is properly configured

## Best Practices

1. **Run in sequence**: Always generate queries → ground truth → evaluation
2. **Backup results**: Keep evaluation results for comparison across iterations
3. **Version control**: Track changes to test queries and ground truth
4. **Regular updates**: Regenerate test data when law database changes
5. **Monitor performance**: Track metric trends across system versions

## Version History

- **v1.0.0** (2025-11-17): Initial release
  - 50 test queries across 4 categories
  - Automated ground truth generation
  - 5 system variants
  - 4 standard IR metrics

## Authors

Law Search System Team

## License

Internal use only
