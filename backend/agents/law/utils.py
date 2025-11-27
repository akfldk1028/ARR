"""
Utility functions for Law Search System
"""

import re
from typing import Dict, Optional, Tuple


def parse_hang_id(hang_id: str) -> Dict[str, str]:
    """
    Parse HANG full_id to extract law information

    Format: "법률명(법률타입)::제N장::제M절::제X조::항Y"
    Example: "국토의 계획 및 이용에 관한 법률(시행령)::제12장::제2절::제36조::항"

    Args:
        hang_id: HANG node full_id

    Returns:
        Dictionary with:
        - law_name: 법률명
        - law_type: 법률/시행령/시행규칙
        - jo_number: 조 번호 (숫자)
        - hang_number: 항 번호 (숫자 또는 None)
        - full_law_id: 법률명(법률타입)
    """
    result = {
        'law_name': 'Unknown',
        'law_type': 'Unknown',
        'jo_number': 'Unknown',
        'hang_number': 'Unknown',
        'full_law_id': 'Unknown'
    }

    if not hang_id:
        return result

    # Split by ::
    parts = hang_id.split('::')

    if len(parts) == 0:
        return result

    # First part contains "법률명(법률타입)"
    first_part = parts[0]

    # Extract law name and type using regex
    # Pattern: "법률명(법률타입)"
    match = re.match(r'(.+?)\((.+?)\)$', first_part)
    if match:
        result['law_name'] = match.group(1).strip()
        result['law_type'] = match.group(2).strip()
        result['full_law_id'] = first_part
    else:
        # Fallback: use entire first part
        result['law_name'] = first_part
        result['law_type'] = 'Unknown'
        result['full_law_id'] = first_part

    # Extract jo_number (조 번호)
    # Look for pattern "제N조" in parts
    for part in parts:
        jo_match = re.search(r'제(\d+)조', part)
        if jo_match:
            result['jo_number'] = jo_match.group(1)
            break

    # Extract hang_number (항 번호)
    # Last part usually contains hang info
    if len(parts) > 0:
        last_part = parts[-1]
        # Pattern: "항" or "항N" or just "N"
        hang_match = re.search(r'항(\d+)|^(\d+)$', last_part)
        if hang_match:
            result['hang_number'] = hang_match.group(1) or hang_match.group(2)
        elif last_part.strip() == '항':
            result['hang_number'] = '1'  # Default to 1 if just "항"

    return result


def enrich_hang_result(result: Dict) -> Dict:
    """
    Enrich HANG search result with parsed law information

    Args:
        result: Search result dict with at minimum 'hang_id' field

    Returns:
        Enriched result with law_name, law_type, jo_number, hang_number fields
    """
    hang_id = result.get('hang_id', '')
    parsed = parse_hang_id(hang_id)

    # Add parsed fields to result
    result['law_name'] = parsed['law_name']
    result['law_type'] = parsed['law_type']
    result['jo_number'] = parsed['jo_number']
    result['hang_number'] = parsed['hang_number']
    result['full_law_id'] = parsed['full_law_id']

    return result


def enrich_hang_results(results: list) -> list:
    """
    Enrich list of HANG search results with parsed law information

    Args:
        results: List of search result dicts

    Returns:
        List of enriched results
    """
    return [enrich_hang_result(result.copy()) for result in results]


def deduplicate_results(results: list) -> list:
    """
    Remove duplicate HANG results based on hang_id

    Keeps the first occurrence (highest ranked) of each unique hang_id

    Args:
        results: List of search results with 'hang_id' field

    Returns:
        Deduplicated list
    """
    seen_ids = set()
    deduplicated = []

    for result in results:
        hang_id = result.get('hang_id')
        if hang_id and hang_id not in seen_ids:
            seen_ids.add(hang_id)
            deduplicated.append(result)

    return deduplicated


def boost_diversity_by_law_type(results: list, target_distribution: Dict[str, float] = None) -> list:
    """
    Re-rank results to ensure diversity across law types (법률, 시행령, 시행규칙)

    Uses interleaving strategy to mix different law types

    Args:
        results: List of enriched results with 'law_type' field
        target_distribution: Optional target percentage for each type
                            Default: {'법률': 0.4, '시행령': 0.3, '시행규칙': 0.3}

    Returns:
        Re-ranked results with better type diversity
    """
    if not results:
        return results

    # Group by law type
    by_type = {}
    for result in results:
        law_type = result.get('law_type', 'Unknown')
        if law_type not in by_type:
            by_type[law_type] = []
        by_type[law_type].append(result)

    # If only one type, return as is
    if len(by_type) <= 1:
        return results

    # Interleave results from different types
    # Strategy: Round-robin through types
    diversified = []
    max_len = max(len(v) for v in by_type.values())

    for i in range(max_len):
        for law_type in sorted(by_type.keys()):  # Sort for consistency
            if i < len(by_type[law_type]):
                diversified.append(by_type[law_type][i])

    return diversified


def format_law_citation(result: Dict) -> str:
    """
    Format a search result as a legal citation

    Example: "국토의 계획 및 이용에 관한 법률 시행령 제36조 제1항"

    Args:
        result: Enriched search result

    Returns:
        Formatted citation string
    """
    law_name = result.get('law_name', 'Unknown')
    law_type = result.get('law_type', '')
    jo_number = result.get('jo_number', '')
    hang_number = result.get('hang_number', '')

    citation = law_name

    if law_type and law_type != '법률':
        citation += f" {law_type}"

    if jo_number and jo_number != 'Unknown':
        citation += f" 제{jo_number}조"

    if hang_number and hang_number != 'Unknown':
        citation += f" 제{hang_number}항"

    return citation
