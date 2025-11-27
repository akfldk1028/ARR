"""
Test unit_path parsing for article number extraction
"""
import re

# Backend에 실제로 있는 utils.py의 parse_hang_id 함수 확인
def parse_hang_id_from_backend(hang_id: str) -> dict:
    """
    Backend agents/law/utils.py의 parse_hang_id 함수
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

    law_name = law_part.replace(f'({law_type})', '').strip()

    return {
        'law_name': law_name,
        'law_type': law_type,
        'full_id': hang_id
    }


def extract_article_from_unit_path(unit_path: str) -> str:
    """
    unit_path에서 조항 번호 추출

    Examples:
        "제12장_제2절_제36조_제" → "제36조"
        "제4장_제36조_제1항" → "제36조 제1항"
        "제36조" → "제36조"
    """
    if not unit_path:
        return ""

    # 패턴: 제N조 찾기
    article_match = re.search(r'제\d+조', unit_path)
    if article_match:
        article = article_match.group()

        # 항/호까지 포함 여부 확인
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

    return ""


# 테스트
test_cases = [
    "제12장_제2절_제36조_제",
    "제12장_제4절_제36조_제",
    "제4장_제36조",
    "제4장_제36조_제1항",
    "제4장_제36조_제1항_제1호",
    "제36조",
]

print("=" * 80)
print("Unit Path Parsing Test")
print("=" * 80)

for unit_path in test_cases:
    article = extract_article_from_unit_path(unit_path)
    print(f"\nInput:  {unit_path}")
    print(f"Output: {article}")

print("\n" + "=" * 80)
print("Testing with Backend parse_hang_id")
print("=" * 80)

test_hang_ids = [
    "국토의 계획 및 이용에 관한 법률(법률)::제12장::제2절::제36조::제",
    "국토의 계획 및 이용에 관한 법률(시행령)::제4장::제36조::제1항",
]

for hang_id in test_hang_ids:
    parsed = parse_hang_id_from_backend(hang_id)
    print(f"\nInput: {hang_id}")
    print(f"Law:   {parsed['law_name']} ({parsed['law_type']})")
