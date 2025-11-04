"""
PDF 법령 텍스트 추출 모듈

PDF 법령 문서에서 텍스트를 추출하여 파싱 가능한 형태로 변환
"""

import re
from pathlib import Path
from typing import Optional, List, Dict
import json


def extract_text_from_pdf_simple(pdf_path: str) -> str:
    """
    PDF에서 텍스트 추출 (PyPDF2 사용)

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        추출된 텍스트
    """
    try:
        import PyPDF2

        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()

        return text
    except ImportError:
        print("PyPDF2가 설치되지 않았습니다: pip install PyPDF2")
        return ""
    except Exception as e:
        print(f"PDF 추출 오류: {e}")
        return ""


def extract_text_from_pdf_advanced(pdf_path: str) -> str:
    """
    PDF에서 텍스트 추출 (pdfplumber 사용 - 더 정확)

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        추출된 텍스트
    """
    try:
        import pdfplumber

        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
                text += "\n"

        return text
    except ImportError:
        print("pdfplumber가 설치되지 않았습니다: pip install pdfplumber")
        # PyPDF2로 폴백
        return extract_text_from_pdf_simple(pdf_path)
    except Exception as e:
        print(f"PDF 추출 오류: {e}")
        return ""


def clean_pdf_text(text: str) -> str:
    """
    PDF에서 추출한 텍스트 정제

    - 페이지 번호 제거
    - 헤더/푸터 제거
    - 불필요한 공백 정리
    """
    # 페이지 번호 패턴 제거 (예: "- 1 -", "1 페이지")
    text = re.sub(r'-\s*\d+\s*-', '', text)
    text = re.sub(r'\d+\s*페이지', '', text)

    # 연속된 공백을 하나로
    text = re.sub(r' +', ' ', text)

    # 연속된 줄바꿈을 2개로 제한
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 각 줄의 앞뒤 공백 제거
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text


def extract_law_name_from_pdf(text: str) -> Optional[str]:
    """
    PDF 텍스트에서 법률명 추출

    예: "건축법", "국토의 계획 및 이용에 관한 법률"
    """
    # 첫 100줄에서 법률명 패턴 찾기
    lines = text.split('\n')[:100]

    # 제외할 키워드 (false positives)
    exclude_keywords = [
        '국가법령정보센터', '법제처', '다른 법률', '타 법률', '해당 법률',
        '관계 법률', '각 법률', '개별 법률', '특별법', '일반법'
    ]

    candidates = []

    for line in lines:
        # "○○법" 패턴 - 독립적인 법률명 매칭
        # 법률명은 보통 줄의 시작이나 괄호 안에 단독으로 나타남
        patterns = [
            r'^([가-힣\s]+(?:법|법률))\s*(?:\(|$)',  # 줄 시작
            r'\s([가-힣\s]+(?:법|법률))\s*\(',  # 괄호 앞
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                law_name = match.group(1).strip()

                # 길이 체크
                if not (5 <= len(law_name) <= 50):
                    continue

                # 제외 키워드 체크
                if any(keyword in law_name or keyword in line for keyword in exclude_keywords):
                    continue

                # 후보에 추가
                candidates.append({
                    'name': law_name,
                    'length': len(law_name),
                    'line': line
                })

    # 가장 긴 법률명 선택 (더 구체적일 가능성이 높음)
    if candidates:
        best_candidate = max(candidates, key=lambda x: x['length'])
        return best_candidate['name']

    return None


def extract_law_type_from_filename(filename: str) -> str:
    """
    파일명에서 법률 유형 추출

    예: "시행령", "시행규칙", "법률"
    """
    if '시행령' in filename:
        return "시행령"
    elif '시행규칙' in filename:
        return "시행규칙"
    else:
        return "법률"


def extract_metadata_from_filename(filename: str) -> Dict[str, Optional[str]]:
    """
    파일명에서 메타데이터 추출

    예: "04_국토의 계획 및 이용에 관한 법률(법률)(제19117호)(20230628).pdf"

    Returns:
        {
            'law_number': '제19117호',
            'enforcement_date': '2023-06-28',
            'law_category': '법률'
        }
    """
    import re

    result = {
        'law_number': None,
        'enforcement_date': None,
        'law_category': None
    }

    # 패턴: 순번_법률명(법률|시행령|시행규칙)(제숫자호)(YYYYMMDD).pdf
    pattern = r'\((법률|시행령|시행규칙)\)\(제(\d+)호\)\((\d{8})\)\.pdf$'
    match = re.search(pattern, filename)

    if match:
        result['law_category'] = match.group(1)
        result['law_number'] = f"제{match.group(2)}호"

        # YYYYMMDD → YYYY-MM-DD 변환
        date_str = match.group(3)
        result['enforcement_date'] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    else:
        # 패턴이 맞지 않으면 기본값
        result['law_category'] = extract_law_type_from_filename(filename)

    return result


def extract_metadata_from_content(text: str) -> Dict[str, Optional[str]]:
    """
    PDF 텍스트에서 메타데이터 추출

    예: "[시행 2023. 6. 28.] [법률 제19117호, 2022. 12. 27., 타법개정]"

    Returns:
        {
            'promulgation_date': '2022-12-27',
            'enforcement_date': '2023-06-28',
            'abbreviation': '국토계획법'
        }
    """
    import re

    result = {
        'promulgation_date': None,
        'enforcement_date': None,
        'abbreviation': None
    }

    # 첫 200줄에서 메타데이터 찾기
    lines = text.split('\n')[:200]
    text_sample = '\n'.join(lines)

    # 시행일 추출: [시행 YYYY. M. D.]
    enforcement_pattern = r'\[시행\s+(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*\]'
    match = re.search(enforcement_pattern, text_sample)
    if match:
        year, month, day = match.groups()
        result['enforcement_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # 공포일 추출: [법률 제숫자호, YYYY. M. D., ...]
    promulgation_pattern = r'\[(?:법률|대통령령|부령)\s+제\d+호,\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.'
    match = re.search(promulgation_pattern, text_sample)
    if match:
        year, month, day = match.groups()
        result['promulgation_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # 약칭 추출: ( 약칭: ○○법 )
    abbrev_pattern = r'\(\s*약칭:\s*([가-힣]+(?:법|령|규칙))\s*\)'
    match = re.search(abbrev_pattern, text_sample)
    if match:
        result['abbreviation'] = match.group(1)

    return result


def extract_base_law_name(law_name: str, abbreviation: Optional[str] = None) -> str:
    """
    모법 이름 추출

    약칭이 있으면 약칭 사용, 없으면 법률명에서 자동 생성

    Args:
        law_name: 전체 법률명 (예: "국토의 계획 및 이용에 관한 법률", "국토의 계획 및 이용에 관한 법률 시행령")
        abbreviation: 약칭 (예: "국토계획법")

    Returns:
        모법 이름 (예: "국토계획법")
    """
    # 1. 약칭이 있으면 사용
    if abbreviation:
        return abbreviation

    # 2. 법률명에서 " 시행령", " 시행규칙" 제거하여 정규화
    normalized_name = law_name
    for suffix in [' 시행령', ' 시행규칙']:
        if normalized_name.endswith(suffix):
            normalized_name = normalized_name[:-len(suffix)]
            break

    # 3. 약칭 매핑 테이블 (확장 가능)
    ABBREVIATION_MAP = {
        "국토의 계획 및 이용에 관한 법률": "국토계획법",
        "건축법": "건축법",
        "주택법": "주택법",
        # 필요에 따라 추가 가능
    }

    # 4. 매핑 테이블에서 찾기
    if normalized_name in ABBREVIATION_MAP:
        return ABBREVIATION_MAP[normalized_name]

    # 5. 매핑이 없으면 정규화된 이름 사용
    return normalized_name


class PDFLawExtractor:
    """PDF 법령 추출기"""

    def __init__(self, use_advanced: bool = True):
        """
        Args:
            use_advanced: True면 pdfplumber 사용, False면 PyPDF2 사용
        """
        self.use_advanced = use_advanced

    def extract(self, pdf_path: str) -> dict:
        """
        PDF에서 법령 정보 추출

        Returns:
            {
                'law_name': str,
                'law_type': str,
                'law_category': str,
                'law_number': str,
                'promulgation_date': str,
                'enforcement_date': str,
                'base_law_name': str,
                'text': str,
                'source_file': str
            }
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

        print(f"PDF 추출 중: {pdf_path.name}")

        # 텍스트 추출
        if self.use_advanced:
            raw_text = extract_text_from_pdf_advanced(str(pdf_path))
        else:
            raw_text = extract_text_from_pdf_simple(str(pdf_path))

        if not raw_text:
            raise ValueError("PDF에서 텍스트를 추출할 수 없습니다")

        # 텍스트 정제
        cleaned_text = clean_pdf_text(raw_text)

        # 법률명 추출
        law_name = extract_law_name_from_pdf(cleaned_text)
        if not law_name:
            # 파일명에서 추출 시도
            law_name = self._extract_law_name_from_filename(pdf_path.name)

        # 파일명에서 메타데이터 추출
        filename_metadata = extract_metadata_from_filename(pdf_path.name)

        # PDF 내용에서 메타데이터 추출
        content_metadata = extract_metadata_from_content(cleaned_text)

        # 법률 유형 (기존 호환성 유지)
        law_type = filename_metadata.get('law_category') or extract_law_type_from_filename(pdf_path.name)

        # 법률 카테고리 (law_type과 동일하지만 명확한 이름)
        law_category = law_type

        # 법령 번호
        law_number = filename_metadata.get('law_number')

        # 시행일 (파일명 우선, 없으면 내용에서)
        enforcement_date = filename_metadata.get('enforcement_date') or content_metadata.get('enforcement_date')

        # 공포일
        promulgation_date = content_metadata.get('promulgation_date')

        # 약칭
        abbreviation = content_metadata.get('abbreviation')

        # 모법 이름
        base_law_name = extract_base_law_name(law_name, abbreviation)

        print(f"추출 완료: {law_name} ({law_category})")
        print(f"법령 번호: {law_number}, 시행일: {enforcement_date}")
        print(f"텍스트 길이: {len(cleaned_text):,} 글자")

        return {
            'law_name': law_name,
            'law_type': law_type,  # 기존 호환성
            'law_category': law_category,
            'law_number': law_number,
            'promulgation_date': promulgation_date,
            'enforcement_date': enforcement_date,
            'base_law_name': base_law_name,
            'text': cleaned_text,
            'source_file': pdf_path.name
        }

    def _extract_law_name_from_filename(self, filename: str) -> str:
        """파일명에서 법률명 추출"""
        # "04_국토의 계획 및 이용에 관한 법률(법률)(제19117호)(20230628).pdf"
        # → "국토의 계획 및 이용에 관한 법률"

        # 숫자_제거
        name = re.sub(r'^\d+_', '', filename)

        # 확장자 제거
        name = name.replace('.pdf', '')

        # 괄호 내용 제거
        name = re.sub(r'\([^)]+\)', '', name)

        return name.strip()

    def extract_multiple(self, pdf_dir: str, pattern: str = "*.pdf") -> List[dict]:
        """
        디렉토리 내 여러 PDF 추출

        Args:
            pdf_dir: PDF 디렉토리 경로
            pattern: 파일 패턴 (예: "*.pdf", "*법률*.pdf")

        Returns:
            추출된 법령 정보 리스트
        """
        pdf_dir = Path(pdf_dir)

        if not pdf_dir.exists():
            raise FileNotFoundError(f"디렉토리를 찾을 수 없습니다: {pdf_dir}")

        pdf_files = list(pdf_dir.glob(pattern))

        if not pdf_files:
            print(f"⚠️  {pdf_dir}에서 '{pattern}' 패턴의 PDF를 찾을 수 없습니다")
            return []

        print(f"\n📚 {len(pdf_files)}개 PDF 파일 발견")
        print("=" * 80)

        results = []
        for pdf_file in sorted(pdf_files):
            try:
                result = self.extract(str(pdf_file))
                results.append(result)
            except Exception as e:
                print(f"❌ {pdf_file.name} 추출 실패: {e}")

        print("\n" + "=" * 80)
        print(f"✅ 총 {len(results)}개 PDF 추출 완료")

        return results


# 사용 예시
if __name__ == "__main__":
    import sys

    # doc 폴더의 PDF 추출
    extractor = PDFLawExtractor(use_advanced=True)

    try:
        # 단일 파일 테스트
        test_file = "doc/04_국토의 계획 및 이용에 관한 법률(법률)(제19117호)(20230628).pdf"

        if Path(test_file).exists():
            print("=== 단일 PDF 테스트 ===")
            result = extractor.extract(test_file)

            print(f"\n법률명: {result['law_name']}")
            print(f"유형: {result['law_type']}")
            print(f"출처: {result['source_file']}")
            print(f"\n텍스트 미리보기 (처음 500자):")
            print(result['text'][:500])
            print("...")

            # JSON 저장
            output_file = f"extracted_{result['law_name']}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n✅ {output_file} 저장 완료")

        # 전체 폴더 테스트
        if Path("doc").exists():
            print("\n\n=== 전체 폴더 테스트 ===")
            results = extractor.extract_multiple("doc")

            # 모두 저장
            with open('extracted_all_laws.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n✅ extracted_all_laws.json 저장 완료 ({len(results)}개 법령)")

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        sys.exit(1)
