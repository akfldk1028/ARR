"""
Law Search Utility Functions

법률 검색 결과 파싱 및 enrichment 유틸리티
"""
import re
from typing import Dict, List, Optional


def parse_hang_id(hang_id: str) -> Dict[str, str]:
    """
    full_id에서 법률 정보 추출

    Args:
        hang_id: HANG 노드의 full_id (e.g., "국토의 계획 및 이용에 관한 법률(법률)::제4장::제36조")

    Returns:
        {
            'law_name': '국토의 계획 및 이용에 관한 법률',
            'law_type': '법률',  # or '시행령', '시행규칙'
            'full_id': hang_id
        }
    """
    parts = hang_id.split('::')

    law_part = parts[0] if len(parts) > 0 else ''
    law_type = ''

    if '법률' in law_part:
        law_type = '법률'
    elif '시행령' in law_part:
        law_type = '시행령'
    elif '시행규칙' in law_part:
        law_type = '시행규칙'

    # 괄호와 법률 타입 제거
    law_name = law_part.replace(f'({law_type})', '').strip()

    return {
        'law_name': law_name,
        'law_type': law_type,
        'full_id': hang_id
    }


def extract_article_from_unit_path(unit_path: str) -> str:
    """
    unit_path에서 사용자 친화적인 조항 번호 추출

    Args:
        unit_path: HANG 노드의 unit_path (e.g., "제12장_제2절_제36조_제")

    Returns:
        조항 번호 문자열 (e.g., "제36조", "제36조 제1항", "제36조 제1항 제1호")

    Examples:
        "제12장_제2절_제36조_제" → "제36조"
        "제4장_제36조_제1항" → "제36조 제1항"
        "제4장_제36조_제1항_제1호" → "제36조 제1항 제1호"
        "제36조" → "제36조"
    """
    if not unit_path:
        return ""

    # 패턴: 제N조 찾기
    article_match = re.search(r'제\d+조', unit_path)
    if not article_match:
        return ""

    article = article_match.group()
    rest = unit_path[article_match.end():]

    # 제N항 찾기
    hang_match = re.search(r'제\d+항', rest)
    if hang_match:
        article += f" {hang_match.group()}"
        rest = rest[hang_match.end():]

        # 제N호 찾기
        ho_match = re.search(r'제\d+호', rest)
        if ho_match:
            article += f" {ho_match.group()}"

    return article


def enrich_search_result(result: Dict) -> Dict:
    """
    검색 결과에 사용자 친화적인 정보 추가

    Args:
        result: {
            'hang_id': str,
            'content': str,
            'unit_path': str,
            'similarity': float
        }

    Returns:
        result에 다음 필드 추가:
        - 'law_name': str (법률 이름)
        - 'law_type': str (법률/시행령/시행규칙)
        - 'article': str (제36조, 제36조 제1항 등)
    """
    # hang_id에서 법률 정보 추출
    hang_id = result.get('hang_id', '')
    parsed = parse_hang_id(hang_id)

    result['law_name'] = parsed['law_name']
    result['law_type'] = parsed['law_type']

    # unit_path에서 조항 번호 추출
    unit_path = result.get('unit_path', '')
    result['article'] = extract_article_from_unit_path(unit_path)

    return result


def enrich_search_results(results: List[Dict]) -> List[Dict]:
    """
    검색 결과 리스트 전체에 enrichment 적용

    Args:
        results: 검색 결과 리스트

    Returns:
        enriched 결과 리스트
    """
    return [enrich_search_result(r) for r in results]


def format_search_result_for_display(result: Dict) -> str:
    """
    검색 결과를 사용자 친화적인 문자열로 포맷팅

    Args:
        result: enriched 검색 결과

    Returns:
        포맷된 문자열 (예: "제36조 (법률) - 내용...")
    """
    article = result.get('article', '조항 미상')
    law_type = result.get('law_type', '')
    content = result.get('content', '')

    # 내용 요약 (최대 100자)
    content_preview = content[:100] + '...' if len(content) > 100 else content

    return f"{article} ({law_type}) - {content_preview}"


# 테스트 함수
def test_utils():
    """유틸리티 함수 테스트"""
    print("=" * 80)
    print("Law Utils Test")
    print("=" * 80)

    # Test 1: parse_hang_id
    test_hang_ids = [
        "국토의 계획 및 이용에 관한 법률(법률)::제12장::제2절::제36조::제",
        "국토의 계획 및 이용에 관한 법률(시행령)::제4장::제36조::제1항",
    ]

    print("\n[Test 1] parse_hang_id")
    for hang_id in test_hang_ids:
        parsed = parse_hang_id(hang_id)
        print(f"\nInput: {hang_id}")
        print(f"Law:   {parsed['law_name']}")
        print(f"Type:  {parsed['law_type']}")

    # Test 2: extract_article_from_unit_path
    test_unit_paths = [
        "제12장_제2절_제36조_제",
        "제4장_제36조_제1항",
        "제4장_제36조_제1항_제1호",
    ]

    print("\n[Test 2] extract_article_from_unit_path")
    for unit_path in test_unit_paths:
        article = extract_article_from_unit_path(unit_path)
        print(f"\nInput:  {unit_path}")
        print(f"Output: {article}")

    # Test 3: enrich_search_result
    test_result = {
        'hang_id': '국토의 계획 및 이용에 관한 법률(법률)::제12장::제2절::제36조::제',
        'unit_path': '제12장_제2절_제36조_제',
        'content': '용도지역에 관한 내용입니다...',
        'similarity': 0.85
    }

    print("\n[Test 3] enrich_search_result")
    enriched = enrich_search_result(test_result.copy())
    print(f"\nOriginal: {test_result}")
    print(f"\nEnriched:")
    print(f"  law_name: {enriched['law_name']}")
    print(f"  law_type: {enriched['law_type']}")
    print(f"  article:  {enriched['article']}")

    # Test 4: format_search_result_for_display
    print("\n[Test 4] format_search_result_for_display")
    formatted = format_search_result_for_display(enriched)
    print(f"\n{formatted}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_utils()
