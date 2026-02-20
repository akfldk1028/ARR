"""
Law Search System Evaluation Module

This module provides comprehensive evaluation tools for the law search platform,
including test query generation, ground truth creation, and performance evaluation.

Components:
- generate_test_queries.py: Generates diverse test queries from Neo4j data
- generate_ground_truth.py: Creates ground truth relevance judgments
- run_evaluation.py: Executes evaluation and computes metrics

Usage:
    python manage.py shell < law/evaluation/generate_test_queries.py
    python manage.py shell < law/evaluation/generate_ground_truth.py
    python manage.py shell < law/evaluation/run_evaluation.py
"""

__version__ = "1.0.0"
