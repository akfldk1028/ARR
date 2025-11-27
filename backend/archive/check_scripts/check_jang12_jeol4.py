"""
제12장 제4절 상세 확인
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# 법률 JSON 파일 읽기
json_file = Path("law/data/parsed/국토의 계획 및 이용에 관한 법률_법률.json")

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 70)
print("법률: 국토의 계획 및 이용에 관한 법률")
print("=" * 70)

# 모든 장 확인
print("\n[1] 모든 장(JANG) 목록:")
jangs = [u for u in data['units'] if u['unit_type'] == 'JANG']
for jang in jangs:
    print(f"  제{jang.get('number', '?')}장: {jang.get('title', 'N/A')}")

# 제12장 찾기
jang12 = [u for u in data['units'] if u['unit_type'] == 'JANG' and u.get('number') == '12']
if jang12:
    print(f"\n[2] 제12장 발견:")
    j12 = jang12[0]
    print(f"  Full ID: {j12['full_id']}")
    print(f"  제목: {j12.get('title', 'N/A')}")
    print(f"  번호: {j12.get('number', 'N/A')}")

    # 제12장의 모든 절 찾기
    jeols_in_12 = [u for u in data['units']
                   if u['unit_type'] == 'JEOL' and '제12장' in u.get('full_id', '')]
    print(f"\n[3] 제12장의 절 목록:")
    for jeol in jeols_in_12:
        print(f"  제{jeol.get('number', '?')}절: {jeol.get('title', 'N/A')}")

    # 제12장 제4절 찾기
    jeol4 = [u for u in data['units']
             if u['unit_type'] == 'JEOL' and u.get('number') == '4' and '제12장' in u.get('full_id', '')]

    if jeol4:
        print(f"\n[4] 제12장 제4절 발견:")
        j4 = jeol4[0]
        print(f"  Full ID: {j4['full_id']}")
        print(f"  제목: {j4.get('title', 'N/A')}")
        print(f"  번호: {j4.get('number', 'N/A')}")

        # 제12장 제4절의 조 찾기
        jos_in_jeol4 = [u for u in data['units']
                        if u['unit_type'] == 'JO' and '제12장::제4절' in u.get('full_id', '')]
        print(f"\n[5] 제12장 제4절의 조 목록:")
        for jo in jos_in_jeol4[:10]:  # 처음 10개만
            print(f"  제{jo.get('number', '?')}조: {jo.get('title', 'N/A')}")

        # 제144조 확인
        jo144 = [u for u in data['units']
                 if u['unit_type'] == 'JO' and u.get('number') == '144']
        if jo144:
            print(f"\n[6] 제144조 발견:")
            j = jo144[0]
            print(f"  Full ID: {j['full_id']}")
            print(f"  제목: {j.get('title', 'N/A')}")
            print(f"  내용: {j.get('content', 'N/A')[:200]}")

            # 제144조의 항 확인
            hangs_144 = [u for u in data['units']
                         if u['unit_type'] == 'HANG' and '제144조' in u.get('full_id', '')]
            print(f"\n  항 목록:")
            for hang in hangs_144:
                print(f"    제{hang.get('number', '?')}항: {hang.get('content', 'N/A')[:60]}...")
    else:
        print("\n[4] 제12장 제4절을 찾을 수 없습니다.")
else:
    print("\n[2] 제12장을 찾을 수 없습니다.")

print("\n" + "=" * 70)
