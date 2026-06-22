"""
Law app - ingestion pipeline + search proxy.

Pipeline modules (law.core.*) are loaded lazily to avoid import errors
when pipeline dependencies (langchain_neo4j, etc.) are not installed.
"""

try:
    from law.core.pdf_extractor import PDFLawExtractor
    from law.core.law_parser import EnhancedKoreanLawParser, LegalUnit, UnitType
    from law.core.neo4j_manager import Neo4jLawLoader
    from law.core.rag_chunker import LegalRAGChunker
    from law.core.converters import (
        units_to_standard_json,
        standard_json_to_neo4j_format
    )
    from law.core.relation_extractor import (
        LawRelationExtractor,
        ArticleRelationExtractor,
        extract_law_relationships_from_jsons
    )
    from law.core.interfaces import (
        PDFExtractorInterface,
        LawParserInterface,
        Neo4jManagerInterface,
        RAGChunkerInterface,
        DataConverterInterface
    )

    __all__ = [
        "PDFLawExtractor",
        "EnhancedKoreanLawParser",
        "LegalUnit",
        "UnitType",
        "Neo4jLawLoader",
        "LegalRAGChunker",
        "units_to_standard_json",
        "standard_json_to_neo4j_format",
        "LawRelationExtractor",
        "ArticleRelationExtractor",
        "extract_law_relationships_from_jsons",
        "PDFExtractorInterface",
        "LawParserInterface",
        "Neo4jManagerInterface",
        "RAGChunkerInterface",
        "DataConverterInterface",
    ]
except ImportError:
    # Pipeline dependencies not installed - proxy views still work
    __all__ = []
