"""
PDF 법령 텍스트 추출 모듈

PDF 법령 문서에서 텍스트를 추출하여 파싱 가능한 형태로 변환
"""

import re
from pathlib import Path
from typing import Optional, List
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

    for line in lines:
        # "○○법" 패턴
        match = re.search(r'([가-힣\s]+법(?:률)?)\s*(?:\(|제|시행령|시행규칙)?', line)
        if match:
            law_name = match.group(1).strip()
            # 너무 짧거나 긴 것 제외
            if 3 <= len(law_name) <= 50:
                return law_name

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
                'text': str,
                'source_file': str
            }
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

        print(f"📄 PDF 추출 중: {pdf_path.name}")

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

        # 법률 유형 추출
        law_type = extract_law_type_from_filename(pdf_path.name)

        print(f"✅ 추출 완료: {law_name} ({law_type})")
        print(f"   텍스트 길이: {len(cleaned_text):,} 글자")

        return {
            'law_name': law_name,
            'law_type': law_type,
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
