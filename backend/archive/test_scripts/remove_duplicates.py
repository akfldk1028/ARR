"""
중복 제거 스크립트 - full_id 기준
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def remove_duplicates(input_file: str):
    """중복 full_id 제거"""

    print("=" * 80)
    print("중복 제거")
    print("=" * 80)

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    units = data['units']
    print(f"\n원본 units: {len(units)}개")

    # full_id로 중복 체크
    seen_ids = set()
    unique_units = []
    duplicates = []

    for unit in units:
        full_id = unit['full_id']
        if full_id in seen_ids:
            duplicates.append(full_id)
            print(f"  [중복 제거] {full_id}")
        else:
            seen_ids.add(full_id)
            unique_units.append(unit)

    print(f"\n중복 발견: {len(duplicates)}개")
    print(f"제거 후: {len(unique_units)}개")

    # 저장
    data['units'] = unique_units
    data['law_info']['total_units'] = len(unique_units)

    output_file = input_file.replace('.json', '_dedup.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n출력: {output_file}")

    # 검증
    final_ids = [u['full_id'] for u in unique_units]
    final_dups = [fid for fid in set(final_ids) if final_ids.count(fid) > 1]

    if final_dups:
        print(f"\n❌ 여전히 중복: {len(final_dups)}개")
    else:
        print(f"\n✅ 중복 없음!")

    return output_file


if __name__ == "__main__":
    input_file = "law/data/parsed/국토의_계획_및_이용에_관한_법률_법률_corrected.json"

    if not Path(input_file).exists():
        print(f"❌ 파일 없음: {input_file}")
        sys.exit(1)

    try:
        output = remove_duplicates(input_file)
        print(f"\n✅ 완료!")
        print(f"\n다음 단계:")
        print(f"1. Neo4j 재로드: python law/scripts/json_to_neo4j.py --input {output}")
        print(f"2. 임베딩 재생성: python law/scripts/add_embeddings_v2.py")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
