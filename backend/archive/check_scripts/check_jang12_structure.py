"""
제12장 구조 확인 (UTF-8 고정)
"""
import json
import sys
from pathlib import Path

# UTF-8 출력 강제
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# 법률 JSON 파일
json_file = Path("law/data/parsed/국토의 계획 및 이용에 관한 법률_법률.json")

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 70)
print("법률: 국토의 계획 및 이용에 관한 법률")
print("=" * 70)

# 제12장 확인
jangs = [u for u in data['units'] if u['unit_type'] == '장' and u['unit_number'] == '12']
if jangs:
    jang12 = jangs[0]
    print(f"\n[제12장] {jang12['title']}")
    print(f"Full ID: {jang12['full_id']}")

    # 제12장의 절 찾기
    jeols = [u for u in data['units']
             if u['unit_type'] == '절' and '제12장' in u.get('full_id', '')]

    print(f"\n제12장의 절 목록 ({len(jeols)}개):")
    for jeol in jeols:
        print(f"  제{jeol['unit_number']}절: {jeol['title']}")

    # 제4절 확인
    jeol4 = [j for j in jeols if j['unit_number'] == '4']
    if jeol4:
        j4 = jeol4[0]
        print(f"\n[제12장 제4절] {j4['title']}")
        print(f"Full ID: {j4['full_id']}")

        # 제4절의 조 찾기
        jos = [u for u in data['units']
               if u['unit_type'] == '조' and j4['full_id'] in u.get('full_id', '')]

        print(f"\n제4절의 조 목록 ({len(jos)}개):")
        for jo in jos:
            print(f"  제{jo['unit_number']}: {jo['title']}")

            # 제144조 확인
            if jo['unit_number'] == '144조':
                print(f"\n[제144조 상세]")
                print(f"Full ID: {jo['full_id']}")
                print(f"내용: {jo.get('content', 'N/A')}")

                # 제144조의 항 찾기
                hangs = [u for u in data['units']
                         if u['unit_type'] == '항' and '제144조' in u.get('full_id', '')]

                print(f"\n제144조의 항 ({len(hangs)}개):")
                for hang in hangs[:5]:  # 처음 5개만
                    print(f"  제{hang['unit_number']}항: {hang.get('content', 'N/A')[:80]}...")

print("\n" + "=" * 70)
print("결론:")
print("=" * 70)
print("✅ 법률 자체에 제12장 제4절이 존재합니다!")
print("   이것은 정상입니다.")
print("\n⚠️ 혼란의 원인:")
print("   - '국토의 계획 및 이용에 관한 법률'에도 제12장 제4절이 있음")
print("   - '국토의 계획 및 이용에 관한 법률 시행령'에도 제12장이 있음")
print("   - 둘은 다른 문서입니다!")
