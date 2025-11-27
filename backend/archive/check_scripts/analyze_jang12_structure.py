"""
제12장 구조 분석 - 왜 제4절이 제12장 아래에 있는가?
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

json_file = Path("law/data/parsed/국토의 계획 및 이용에 관한 법률_법률.json")

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("전체 장(章) 구조 분석")
print("=" * 80)

# 모든 장 찾기
jangs = [u for u in data['units'] if u['unit_type'] == '장']
print(f"\n총 {len(jangs)}개 장:")
for jang in jangs:
    print(f"  제{jang['unit_number']}장: {jang['title']}")

# 제12장 찾기
jang12 = [u for u in data['units'] if u['unit_type'] == '장' and u['unit_number'] == '12']
if jang12:
    j12 = jang12[0]
    print(f"\n{'='*80}")
    print(f"제12장 상세 정보")
    print(f"{'='*80}")
    print(f"Full ID: {j12['full_id']}")
    print(f"Title: {j12['title']}")
    print(f"Parent ID: {j12['parent_id']}")
    print(f"Line Number: {j12['metadata']['line_number']}")

    # 제12장의 절 찾기
    jeols = [u for u in data['units']
             if u['unit_type'] == '절' and u['parent_id'] == j12['full_id']]

    print(f"\n제12장에 속한 절 ({len(jeols)}개):")
    for jeol in jeols:
        print(f"  제{jeol['unit_number']}절: {jeol['title']}")
        print(f"    Full ID: {jeol['full_id']}")
        print(f"    Line Number: {jeol['metadata']['line_number']}")

        # 각 절에 속한 조 개수
        jos = [u for u in data['units']
               if u['unit_type'] == '조' and u['parent_id'] == jeol['full_id']]
        print(f"    조 개수: {len(jos)}개")

        if jos:
            print(f"    첫 조: 제{jos[0]['unit_number']} ({jos[0].get('title', 'N/A')})")
            print(f"    마지막 조: 제{jos[-1]['unit_number']} ({jos[-1].get('title', 'N/A')})")

    # 제12장에 직접 속한 조 (절 없이)
    jos_direct = [u for u in data['units']
                  if u['unit_type'] == '조' and u['parent_id'] == j12['full_id']]

    if jos_direct:
        print(f"\n제12장에 직접 속한 조 (절 없이): {len(jos_direct)}개")
        for jo in jos_direct[:5]:
            print(f"  제{jo['unit_number']}: {jo.get('title', 'N/A')}")

print(f"\n{'='*80}")
print("문제 분석")
print(f"{'='*80}")
print("\n제12장 = '벌칙'인데, 제4절 = '지구단위계획'?")
print("→ 이것은 명백히 잘못된 구조입니다!")
print("\n가능한 원인:")
print("1. PDF 텍스트 추출 시 순서가 뒤섞임")
print("2. PDF 레이아웃 (컬럼, 페이지) 문제로 잘못 읽힘")
print("3. 파싱 로직의 컨텍스트 관리 오류")
print("\n해결 방법:")
print("1. 원본 PDF의 실제 구조 확인")
print("2. PDF 추출된 텍스트 확인")
print("3. 파싱 로직 검증")
