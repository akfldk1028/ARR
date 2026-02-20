"""
추상 인터페이스 정의
나중에 다양한 구현체로 교체 가능하도록 설계
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path


class PDFExtractorInterface(ABC):
    """PDF 텍스트 추출 인터페이스"""

    @abstractmethod
    def extract(self, pdf_path: str) -> Dict[str, Any]:
        """
        PDF에서 텍스트 추출

        Args:
            pdf_path: PDF 파일 경로

        Returns:
            {
                "law_name": str,
                "law_type": str,
                "text": str,
                "source_file": str
            }
        """
        pass


class LawParserInterface(ABC):
    """법령 파싱 인터페이스"""

    @abstractmethod
    def parse(self, text: str) -> List[Any]:
        """
        텍스트를 법령 단위로 파싱

        Args:
            text: 원문 텍스트

        Returns:
            LegalUnit 객체 리스트
        """
        pass


class Neo4jManagerInterface(ABC):
    """Neo4j 저장 인터페이스"""

    @abstractmethod
    def create_constraints_and_indexes(self) -> None:
        """제약조건 및 인덱스 생성"""
        pass

    @abstractmethod
    def load_law_data(self, law_data: Dict[str, Any]) -> Dict[str, int]:
        """
        법령 데이터를 Neo4j에 저장

        Args:
            law_data: Neo4j 형식의 법령 데이터

        Returns:
            {"nodes_created": int, "relationships_created": int}
        """
        pass


class RAGChunkerInterface(ABC):
    """RAG 청킹 인터페이스"""

    @abstractmethod
    def chunk(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        표준 JSON을 RAG 청크로 변환

        Args:
            data: 표준 JSON 형식 데이터

        Returns:
            청크 리스트
        """
        pass


class DataConverterInterface(ABC):
    """데이터 형식 변환 인터페이스"""

    @abstractmethod
    def to_standard_json(self, units: List[Any], **metadata) -> Dict[str, Any]:
        """
        파싱된 units를 표준 JSON으로 변환

        Args:
            units: 파싱된 법령 단위 리스트
            **metadata: 메타데이터 (law_name, law_type 등)

        Returns:
            표준 JSON 딕셔너리
        """
        pass

    @abstractmethod
    def to_neo4j_format(self, standard_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        표준 JSON을 Neo4j 형식으로 변환

        Args:
            standard_json: 표준 JSON 데이터

        Returns:
            Neo4j 형식 딕셔너리
        """
        pass
