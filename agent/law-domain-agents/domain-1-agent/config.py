"""
Configuration for Domain 1 Agent

Domain: 도시계획 및 이용
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Domain1Config:
    """Configuration for Domain 1: 도시계획 및 이용"""

    # Domain Identity
    DOMAIN_ID = os.getenv("DOMAIN_1_ID", "domain_1")
    DOMAIN_NAME = os.getenv("DOMAIN_1_NAME", "도시계획 및 이용")
    DOMAIN_DESCRIPTION = os.getenv(
        "DOMAIN_1_DESCRIPTION",
        "국토계획법 도시계획 및 이용 관련 법률 조항 검색 전문 에이전트"
    )
    DOMAIN_PORT = int(os.getenv("DOMAIN_1_PORT", "8011"))

    # Search Configuration
    RNE_THRESHOLD = float(os.getenv("RNE_THRESHOLD", "0.75"))
    INE_K = int(os.getenv("INE_K", "10"))
    MAX_EXPANSION_DEPTH = int(os.getenv("MAX_EXPANSION_DEPTH", "2"))

    # LLM Configuration
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    # KR-SBERT Model
    KR_SBERT_MODEL = os.getenv("KR_SBERT_MODEL", "snunlp/KR-SBERT-V40K-klueNLI-augSTS")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def get_agent_card(cls) -> dict:
        """
        Generate A2A agent card

        Returns:
            Agent card dictionary compliant with A2A protocol
        """
        return {
            "capabilities": {
                "search": {
                    "description": "법률 조항 검색 (RNE + INE 알고리즘)",
                    "methods": ["semantic_search", "graph_expansion"]
                },
                "analysis": {
                    "description": "법률 조항 분석 및 해석",
                    "methods": ["llm_analysis"]
                }
            },
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "description": cls.DOMAIN_DESCRIPTION,
            "name": f"Domain1Agent_{cls.DOMAIN_NAME}",
            "preferredTransport": "JSONRPC",
            "protocolVersion": "0.3.0",
            "skills": [
                {
                    "description": cls.DOMAIN_DESCRIPTION,
                    "id": cls.DOMAIN_ID,
                    "name": cls.DOMAIN_NAME,
                    "tags": ["law", "search", "korean", "neo4j", "semantic"]
                }
            ],
            "supportsAuthenticatedExtendedCard": False,
            "url": f"http://localhost:{cls.DOMAIN_PORT}/messages",
            "version": "0.1.0"
        }


# Export singleton config instance
config = Domain1Config()
