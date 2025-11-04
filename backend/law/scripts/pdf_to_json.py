"""
Step 1: PDF → 표준 법규 JSON

PDF 법령을 1차 파싱하여 표준 JSON 형식으로 저장
나중에 Neo4j나 RAG로 변환 가능
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import sys

from pdf_extractor import PDFLawExtractor
from neo4j_preprocessor import EnhancedKoreanLawParser


def units_to_standard_json(law_name: str, law_type: str, source_file: str, units: List) -> Dict:
    """
    파싱된 units를 표준 JSON 형식으로 변환

    Args:
        law_name: 법률명
        law_type: 법률 유형 ("법률", "시행령", "시행규칙")
        source_file: 원본 파일명
        units: 파싱된 LegalUnit 객체 리스트

    Returns:
        표준 JSON 딕셔너리
    """
    standard_json = {
        "law_info": {
            "law_name": law_name,
            "law_type": law_type,
            "source_file": source_file,
            "parsed_at": datetime.now().isoformat(),
            "total_units": len(units)
        },
        "units": []
    }

    for unit in units:
        unit_dict = {
            "unit_type": unit.unit_type.value,  # "조", "항", "호", "목" 등
            "unit_number": unit.unit_number,
            "title": unit.title,
            "content": unit.content,
            "unit_path": unit.unit_path,
            "full_id": unit.full_id,
            "parent_id": unit.parent_id,
            "order": unit.order,
            "revision_dates": unit.revision_dates,
            "metadata": unit.metadata
        }

        standard_json["units"].append(unit_dict)

    return standard_json


def safe_filename(name: str) -> str:
    """
    파일명으로 사용 가능하도록 변환

    예: "국토의 계획 및 이용에 관한 법률" → "국토의_계획_및_이용에_관한_법률"
    """
    return name.replace(" ", "_").replace("/", "_").replace("\\", "_")


def pdf_to_json(pdf_path: str, output_dir: str = "law/data/parsed") -> str:
    """
    PDF를 표준 JSON으로 변환

    Args:
        pdf_path: PDF 파일 경로
        output_dir: 출력 디렉토리

    Returns:
        생성된 JSON 파일 경로
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    # 출력 디렉토리 생성
    output_dir.mkdir(exist_ok=True)

    print(f"\n{'='*80}")
    print(f"Step 1: PDF → 표준 JSON")
    print(f"{'='*80}")

    # 1. PDF에서 텍스트 추출
    print(f"\n[1/3] PDF 텍스트 추출 중...")
    extractor = PDFLawExtractor(use_advanced=True)

    try:
        extracted = extractor.extract(str(pdf_path))
    except Exception as e:
        print(f"❌ PDF 추출 실패: {e}")
        raise

    law_name = extracted['law_name']
    law_type = extracted['law_type']
    text = extracted['text']

    print(f"✅ 추출 완료: {law_name} ({law_type})")
    print(f"   텍스트 길이: {len(text):,} 글자")

    # 2. 텍스트 파싱
    print(f"\n[2/3] 법령 파싱 중...")
    parser = EnhancedKoreanLawParser(law_name=law_name, law_type=law_type)

    try:
        units = parser.parse(text)
    except Exception as e:
        print(f"❌ 파싱 실패: {e}")
        raise

    print(f"✅ 파싱 완료: {len(units)}개 법령 단위")

    # 단위 타입별 통계
    unit_types = {}
    for unit in units:
        unit_type = unit.unit_type.value
        unit_types[unit_type] = unit_types.get(unit_type, 0) + 1

    print(f"   단위 타입별 통계:")
    for unit_type, count in sorted(unit_types.items()):
        print(f"     {unit_type}: {count}개")

    # 3. 표준 JSON 저장
    print(f"\n[3/3] 표준 JSON 저장 중...")

    standard_json = units_to_standard_json(
        law_name=law_name,
        law_type=law_type,
        source_file=pdf_path.name,
        units=units
    )

    # 파일명 생성
    safe_law_name = safe_filename(law_name)
    safe_law_type = safe_filename(law_type)
    output_filename = f"{safe_law_name}_{safe_law_type}.json"
    output_path = output_dir / output_filename

    # JSON 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(standard_json, f, ensure_ascii=False, indent=2)

    file_size = output_path.stat().st_size / 1024  # KB

    print(f"✅ 저장 완료: {output_path}")
    print(f"   파일 크기: {file_size:.1f} KB")

    print(f"\n{'='*80}")
    print(f"✅ Step 1 완료!")
    print(f"{'='*80}")

    return str(output_path)


def process_multiple_pdfs(pdf_dir: str = "doc", output_dir: str = "parsed", pattern: str = "*.pdf"):
    """
    여러 PDF를 일괄 처리

    Args:
        pdf_dir: PDF 디렉토리
        output_dir: 출력 디렉토리
        pattern: 파일 패턴
    """
    pdf_dir = Path(pdf_dir)

    if not pdf_dir.exists():
        print(f"❌ 디렉토리를 찾을 수 없습니다: {pdf_dir}")
        return

    pdf_files = list(pdf_dir.glob(pattern))

    if not pdf_files:
        print(f"⚠️  {pdf_dir}에서 '{pattern}' 패턴의 PDF를 찾을 수 없습니다")
        return

    print(f"\n{'='*80}")
    print(f"일괄 처리: {len(pdf_files)}개 PDF 파일")
    print(f"{'='*80}")

    results = []
    errors = []

    for i, pdf_file in enumerate(sorted(pdf_files), 1):
        print(f"\n[{i}/{len(pdf_files)}] {pdf_file.name}")

        try:
            output_path = pdf_to_json(str(pdf_file), output_dir)
            results.append(output_path)
        except Exception as e:
            print(f"❌ 실패: {e}")
            errors.append((pdf_file.name, str(e)))

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

    if results:
        print(f"\n생성된 파일:")
        for path in results:
            print(f"  - {path}")


# 사용 예시
if __name__ == "__main__":
    import argparse

    # UTF-8 출력 설정
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="PDF 법령을 표준 JSON으로 변환")
    parser.add_argument("--pdf", type=str, help="변환할 PDF 파일 경로")
    parser.add_argument("--dir", type=str, default="doc", help="PDF 디렉토리 (기본: doc)")
    parser.add_argument("--output", type=str, default="law/data/parsed", help="출력 디렉토리 (기본: law/data/parsed)")
    parser.add_argument("--pattern", type=str, default="*.pdf", help="파일 패턴 (기본: *.pdf)")
    parser.add_argument("--all", action="store_true", help="디렉토리 내 모든 PDF 처리")

    args = parser.parse_args()

    try:
        if args.pdf:
            # 단일 파일 처리
            pdf_to_json(args.pdf, args.output)
        elif args.all:
            # 전체 디렉토리 처리
            process_multiple_pdfs(args.dir, args.output, args.pattern)
        else:
            # 기본: doc 폴더 처리
            if Path(args.dir).exists():
                process_multiple_pdfs(args.dir, args.output, args.pattern)
            else:
                print(f"사용법:")
                print(f"  단일 파일: python pdf_to_json.py --pdf <파일경로>")
                print(f"  전체 처리: python pdf_to_json.py --all")
                print(f"  디렉토리: python pdf_to_json.py --dir <디렉토리> --all")

    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)
