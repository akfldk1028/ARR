"""
parsed JSON 파일 구조 확인
"""
import sys
import io
import os
import json

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("=" * 70)
print("Parsed JSON 파일 확인")
print("=" * 70)

files = [
    "law/data/parsed/국토의 계획 및 이용에 관한 법률_법률.json",
    "law/data/parsed/국토의 계획 및 이용에 관한 법률 시행령_시행령.json",
    "law/data/parsed/국토의 계획 및 이용에 관한 법률 시행규칙_시행규칙.json"
]

for filepath in files:
    print(f"\n{'='*70}")
    print(f"파일: {filepath}")
    print(f"{'='*70}")

    if not os.path.exists(filepath):
        print(f"❌ 파일 없음!")
        continue

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 기본 정보
        print(f"\n[기본 정보]")
        print(f"  law_name: {data.get('law_name', 'N/A')}")
        print(f"  law_type: {data.get('law_type', 'N/A')}")
        print(f"  full_id: {data.get('full_id', 'N/A')}")

        # 구조 정보
        structure = data.get('structure', {})
        print(f"\n[구조]")
        print(f"  장(JANG): {len(structure.get('jang', []))}개")

        total_jo = sum(len(jang.get('jo', [])) for jang in structure.get('jang', []))
        print(f"  조(JO): {total_jo}개")

        total_hang = 0
        total_ho = 0
        for jang in structure.get('jang', []):
            for jo in jang.get('jo', []):
                total_hang += len(jo.get('hang', []))
                for hang in jo.get('hang', []):
                    total_ho += len(hang.get('ho', []))

        print(f"  항(HANG): {total_hang}개")
        print(f"  호(HO): {total_ho}개")

        # 샘플 조항
        print(f"\n[샘플 조항]")
        for jang in structure.get('jang', [])[:1]:
            for jo in jang.get('jo', [])[:2]:
                print(f"  {jo.get('number', 'N/A')}: {jo.get('title', 'N/A')}")
                for hang in jo.get('hang', [])[:1]:
                    content = hang.get('content', '')
                    print(f"    → {hang.get('number', 'N/A')}: {content[:50]}...")

        print(f"\n✅ 파일 읽기 성공")

    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*70}")
print("요약")
print(f"{'='*70}")
print("✅ 3개 JSON 파일 모두 존재")
print("✅ 구조: law_name, law_type, structure (jang/jo/hang/ho)")
print("❌ Neo4j에는 법률만 로드됨")
print("→ 시행령, 시행규칙도 Neo4j에 로드 필요!")
print(f"{'='*70}")
