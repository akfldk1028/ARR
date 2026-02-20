"""
Step 2b: 표준 JSON → RAG 청크

표준 법규 JSON을 RAG 시스템용 청크로 변환
법적 맥락을 보존하며 다중 레벨 청킹
"""

import json
from pathlib import Path
from typing import Dict, List
import sys


def reconstruct_units_from_json(data: Dict) -> List:
    """
    표준 JSON에서 LegalUnit 객체 재구성

    Args:
        data: 표준 JSON 데이터

    Returns:
        유사 LegalUnit 객체 리스트 (딕셔너리)
    """
    from dataclasses import make_dataclass
    from enum import Enum

    # UnitType Enum 재생성
    UnitType = Enum('UnitType', {
        'LAW': '법률',
        'PYEON': '편',
        'JANG': '장',
        'JEOL': '절',
        'GWAN': '관',
        'JO': '조',
        'HANG': '항',
        'HO': '호',
        'MOK': '목'
    })

    # LegalUnit 클래스 재생성
    LegalUnit = make_dataclass('LegalUnit', [
        ('unit_type', object),
        ('unit_number', str),
        ('title', object),
        ('content', str),
        ('unit_path', str),
        ('full_id', str),
        ('parent_id', object),
        ('order', int),
        ('revision_dates', list),
        ('metadata', dict)
    ])

    units = []
    for unit_data in data['units']:
        # unit_type 문자열을 Enum으로 변환
        unit_type_str = unit_data['unit_type'].upper()
        if unit_type_str in UnitType.__members__:
            unit_type = UnitType[unit_type_str]
        else:
            # 기본값
            unit_type = UnitType.JO

        unit = LegalUnit(
            unit_type=unit_type,
            unit_number=unit_data['unit_number'],
            title=unit_data['title'],
            content=unit_data['content'],
            unit_path=unit_data['unit_path'],
            full_id=unit_data['full_id'],
            parent_id=unit_data['parent_id'],
            order=unit_data['order'],
            revision_dates=unit_data['revision_dates'],
            metadata=unit_data['metadata']
        )

        units.append(unit)

    return units


def chunk_from_standard_json(data: Dict) -> List[Dict]:
    """
    표준 JSON에서 RAG 청크 생성

    legal_chunker_v2.py의 로직을 사용하지만,
    JSON에서 직접 청크를 생성하도록 최적화

    Args:
        data: 표준 JSON 데이터

    Returns:
        청크 리스트
    """
    chunks = []
    chunk_counter = 0

    law_info = data['law_info']
    units = data['units']

    # 조(JO) 단위로 그룹화
    jo_groups = []
    current_jo = None
    current_jo_children = []

    for unit in units:
        if unit['unit_type'] == '조':
            # 이전 조 저장
            if current_jo:
                jo_groups.append((current_jo, current_jo_children))
            current_jo = unit
            current_jo_children = []
        elif current_jo:
            current_jo_children.append(unit)

    # 마지막 조 저장
    if current_jo:
        jo_groups.append((current_jo, current_jo_children))

    # 각 조에 대해 청크 생성
    for jo, jo_children in jo_groups:
        # Level 1: 조 전체 청크
        chunk_counter += 1
        jo_chunk = create_jo_chunk(jo, jo_children, chunk_counter, law_info)
        chunks.append(jo_chunk)

        # Level 2: 항별 청크
        hang_groups = []
        current_hang = None
        current_hang_children = []

        for unit in jo_children:
            if unit['unit_type'] == '항':
                if current_hang:
                    hang_groups.append((current_hang, current_hang_children))
                current_hang = unit
                current_hang_children = []
            elif current_hang and unit['unit_type'] in ['호', '목']:
                current_hang_children.append(unit)

        if current_hang:
            hang_groups.append((current_hang, current_hang_children))

        for hang, hang_children in hang_groups:
            chunk_counter += 1
            hang_chunk = create_hang_chunk(jo, hang, hang_children, chunk_counter, law_info)
            chunks.append(hang_chunk)

            # Level 3: 호별 청크
            ho_groups = []
            current_ho = None
            current_ho_children = []

            for unit in hang_children:
                if unit['unit_type'] == '호':
                    if current_ho:
                        ho_groups.append((current_ho, current_ho_children))
                    current_ho = unit
                    current_ho_children = []
                elif current_ho and unit['unit_type'] == '목':
                    current_ho_children.append(unit)

            if current_ho:
                ho_groups.append((current_ho, current_ho_children))

            for ho, mok_children in ho_groups:
                chunk_counter += 1
                ho_chunk = create_ho_chunk(jo, hang, ho, mok_children, chunk_counter, law_info)
                chunks.append(ho_chunk)

    return chunks


def create_jo_chunk(jo: Dict, children: List[Dict], chunk_id: int, law_info: Dict) -> Dict:
    """조 전체 청크 생성"""
    jo_title = f"제{jo['unit_number']}"
    if jo['title']:
        jo_title += f"({jo['title']})"

    content_parts = [jo_title]
    for child in children:
        content_parts.append(format_unit_content(child))

    content = " ".join(content_parts)

    return {
        "chunk_id": f"chunk_{chunk_id:05d}",
        "chunk_level": "조전체",
        "content": content,
        "source_ids": [jo['full_id']] + [c['full_id'] for c in children],
        "metadata": {
            "law_name": law_info['law_name'],
            "law_type": law_info['law_type'],
            "jo_number": jo['unit_number'],
            "jo_title": jo['title'],
            "jo_id": jo['full_id'],
            "unit_count": 1 + len(children),
            "revision_dates": jo['revision_dates']
        }
    }


def create_hang_chunk(jo: Dict, hang: Dict, children: List[Dict], chunk_id: int, law_info: Dict) -> Dict:
    """항 단위 청크 생성"""
    jo_title = f"제{jo['unit_number']}"
    if jo['title']:
        jo_title += f"({jo['title']})"

    hang_content = clean_content(hang['content'])

    content_parts = [jo_title, f"{hang['unit_number']} {hang_content}"]
    for child in children:
        content_parts.append(format_unit_content(child))

    content = " ".join(content_parts)

    return {
        "chunk_id": f"chunk_{chunk_id:05d}",
        "chunk_level": "항단위",
        "content": content,
        "source_ids": [jo['full_id'], hang['full_id']] + [c['full_id'] for c in children],
        "metadata": {
            "law_name": law_info['law_name'],
            "law_type": law_info['law_type'],
            "jo_number": jo['unit_number'],
            "jo_title": jo['title'],
            "jo_id": jo['full_id'],
            "hang_number": hang['unit_number'],
            "hang_id": hang['full_id'],
            "unit_count": 2 + len(children),
            "revision_dates": hang['revision_dates']
        }
    }


def create_ho_chunk(jo: Dict, hang: Dict, ho: Dict, mok_children: List[Dict], chunk_id: int, law_info: Dict) -> Dict:
    """호 단위 청크 생성"""
    jo_title = f"제{jo['unit_number']}"
    if jo['title']:
        jo_title += f"({jo['title']})"

    # 항 도입부 추출 (처음 100자)
    hang_intro = clean_content(hang['content'])[:100]

    ho_content = clean_content(ho['content'])

    content_parts = [
        jo_title,
        f"{hang['unit_number']} {hang_intro}",
        f"{ho['unit_number']}. {ho_content}"
    ]

    for mok in mok_children:
        content_parts.append(format_unit_content(mok))

    content = " ".join(content_parts)

    return {
        "chunk_id": f"chunk_{chunk_id:05d}",
        "chunk_level": "호단위",
        "content": content,
        "source_ids": [jo['full_id'], hang['full_id'], ho['full_id']] +
                     [m['full_id'] for m in mok_children],
        "metadata": {
            "law_name": law_info['law_name'],
            "law_type": law_info['law_type'],
            "jo_number": jo['unit_number'],
            "jo_title": jo['title'],
            "jo_id": jo['full_id'],
            "hang_number": hang['unit_number'],
            "hang_id": hang['full_id'],
            "ho_number": ho['unit_number'],
            "ho_id": ho['full_id'],
            "unit_count": 3 + len(mok_children),
            "referenced_laws": ho['metadata'].get('referenced_laws', [])
        }
    }


def format_unit_content(unit: Dict) -> str:
    """단위 내용 포맷팅"""
    content = clean_content(unit['content'])

    if unit['unit_type'] == '항':
        return f"{unit['unit_number']} {content}"
    elif unit['unit_type'] == '호':
        return f"{unit['unit_number']}. {content}"
    elif unit['unit_type'] == '목':
        return f"{unit['unit_number']}. {content}"
    else:
        return content


def clean_content(text: str) -> str:
    """개정 표시 등 제거"""
    import re
    return re.sub(r'<[^>]+>', '', text).strip()


def json_to_rag(json_path: str, output_dir: str = "rag") -> str:
    """
    표준 JSON을 RAG 청크로 변환

    Args:
        json_path: 표준 JSON 파일 경로
        output_dir: 출력 디렉토리

    Returns:
        생성된 청크 JSON 파일 경로
    """
    json_path = Path(json_path)
    output_dir = Path(output_dir)

    # 출력 디렉토리 생성
    output_dir.mkdir(exist_ok=True)

    print(f"\n{'='*80}")
    print(f"Step 2b: 표준 JSON → RAG 청크")
    print(f"{'='*80}")

    # 1. JSON 읽기
    print(f"\n[1/3] JSON 읽기 중...")
    with open(json_path, 'r', encoding='utf-8') as f:
        standard_json = json.load(f)

    law_info = standard_json['law_info']
    print(f"✅ {law_info['law_name']} ({law_info['law_type']})")
    print(f"   법령 단위: {law_info['total_units']}개")

    # 2. RAG 청크 생성
    print(f"\n[2/3] RAG 청크 생성 중...")
    chunks = chunk_from_standard_json(standard_json)

    print(f"✅ 청크 생성 완료: {len(chunks)}개")

    # 레벨별 통계
    level_stats = {}
    for chunk in chunks:
        level = chunk['chunk_level']
        level_stats[level] = level_stats.get(level, 0) + 1

    print(f"   레벨별 분포:")
    for level, count in sorted(level_stats.items()):
        print(f"     {level}: {count}개")

    # 3. JSON 저장
    print(f"\n[3/3] 청크 JSON 저장 중...")

    safe_law_name = law_info['law_name'].replace(" ", "_")
    output_filename = f"{safe_law_name}_chunks.json"
    output_path = output_dir / output_filename

    # 전체 정보 포함하여 저장
    output_data = {
        "law_info": law_info,
        "chunks": chunks,
        "total_chunks": len(chunks)
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    file_size = output_path.stat().st_size / 1024  # KB

    print(f"✅ 저장 완료: {output_path}")
    print(f"   파일 크기: {file_size:.1f} KB")

    print(f"\n{'='*80}")
    print(f"✅ Step 2b 완료!")
    print(f"{'='*80}")

    return str(output_path)


def process_multiple_jsons(json_dir: str = "parsed", output_dir: str = "rag", pattern: str = "*.json"):
    """
    여러 JSON을 일괄 처리

    Args:
        json_dir: JSON 디렉토리
        output_dir: 출력 디렉토리
        pattern: 파일 패턴
    """
    json_dir = Path(json_dir)

    if not json_dir.exists():
        print(f"❌ 디렉토리를 찾을 수 없습니다: {json_dir}")
        return

    json_files = list(json_dir.glob(pattern))

    if not json_files:
        print(f"⚠️  {json_dir}에서 '{pattern}' 패턴의 JSON을 찾을 수 없습니다")
        return

    print(f"\n{'='*80}")
    print(f"일괄 처리: {len(json_files)}개 JSON 파일")
    print(f"{'='*80}")

    results = []
    errors = []

    for i, json_file in enumerate(sorted(json_files), 1):
        print(f"\n[{i}/{len(json_files)}] {json_file.name}")

        try:
            output_path = json_to_rag(str(json_file), output_dir)
            results.append(output_path)
        except Exception as e:
            print(f"❌ 실패: {e}")
            errors.append((json_file.name, str(e)))

    # 최종 요약
    print(f"\n{'='*80}")
    print(f"일괄 처리 완료")
    print(f"{'='*80}")
    print(f"성공: {len(results)}개")
    print(f"실패: {len(errors)}개")

    if errors:
        print(f"\n실패한 파일:")
        for filename, error in errors:
            print(f"  - {filename}: {error}")


# 사용 예시
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="표준 JSON을 RAG 청크로 변환")
    parser.add_argument("--json", type=str, help="변환할 JSON 파일 경로")
    parser.add_argument("--dir", type=str, default="parsed", help="JSON 디렉토리 (기본: parsed)")
    parser.add_argument("--output", type=str, default="rag", help="출력 디렉토리 (기본: rag)")
    parser.add_argument("--all", action="store_true", help="디렉토리 내 모든 JSON 처리")

    args = parser.parse_args()

    try:
        if args.json:
            # 단일 파일 처리
            json_to_rag(args.json, args.output)
        elif args.all:
            # 전체 디렉토리 처리
            process_multiple_jsons(args.dir, args.output)
        else:
            print(f"사용법:")
            print(f"  단일 파일: python json_to_rag.py --json <파일경로>")
            print(f"  전체 처리: python json_to_rag.py --all")

    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)
