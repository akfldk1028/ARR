"""
임베딩 모델 로더 - Parser app의 load_embedding_model() 구조 적용
다양한 임베딩 모델 지원 (OpenAI, HuggingFace, ko-sbert-sts)
"""
import os
import logging
from typing import Tuple, Any

logger = logging.getLogger(__name__)


def load_embedding_model(embedding_model_name: str = None) -> Tuple[Any, int]:
    """
    임베딩 모델 로드 - 환경 변수 또는 인자로 모델 선택

    Args:
        embedding_model_name: 임베딩 모델 이름
            - "openai": OpenAI text-embedding-3-large (1536 차원, API 호출)
            - "openai-small": OpenAI text-embedding-3-small (1536 차원, 저렴)
            - "ko-sbert": 한국어 ko-sbert-sts (768 차원, 로컬)
            - None or others: HuggingFace all-MiniLM-L6-v2 (384 차원, 기본값)

    Returns:
        (embeddings_model, dimension): 임베딩 모델 객체와 차원 수
    """
    # 환경 변수에서 읽기 (인자가 없으면)
    if embedding_model_name is None:
        embedding_model_name = os.getenv("LAW_EMBEDDING_MODEL", "ko-sbert")

    logger.info(f"임베딩 모델 선택: {embedding_model_name}")

    if embedding_model_name == "openai":
        try:
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-large"
            )
            dimension = 3072  # text-embedding-3-large default dimension
            logger.info(f"✅ Embedding: OpenAI text-embedding-3-large, Dimension: {dimension}")
            logger.warning("⚠️ OpenAI 임베딩은 API 호출마다 비용 발생 ($0.13 per 1M tokens)")
            return embeddings, dimension
        except ImportError:
            logger.error("langchain_openai not installed. Run: pip install langchain-openai")
            raise

    elif embedding_model_name == "openai-small":
        try:
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small"
            )
            dimension = 1536
            logger.info(f"✅ Embedding: OpenAI text-embedding-3-small, Dimension: {dimension}")
            logger.warning("⚠️ OpenAI 임베딩은 API 호출마다 비용 발생 ($0.02 per 1M tokens)")
            return embeddings, dimension
        except ImportError:
            logger.error("langchain_openai not installed. Run: pip install langchain-openai")
            raise

    elif embedding_model_name == "ko-sbert":
        try:
            from sentence_transformers import SentenceTransformer

            # Wrapper class to match LangChain interface
            class SentenceTransformerWrapper:
                def __init__(self, model_name: str):
                    self.model = SentenceTransformer(model_name)

                def embed_query(self, text: str):
                    """단일 텍스트 임베딩"""
                    return self.model.encode(text, convert_to_numpy=True).tolist()

                def embed_documents(self, texts: list):
                    """여러 텍스트 임베딩 (배치)"""
                    embeddings = self.model.encode(
                        texts,
                        batch_size=32,
                        show_progress_bar=False,
                        convert_to_numpy=True
                    )
                    return [emb.tolist() for emb in embeddings]

            embeddings = SentenceTransformerWrapper("jhgan/ko-sbert-sts")
            dimension = 768
            logger.info(f"✅ Embedding: 한국어 ko-sbert-sts (로컬), Dimension: {dimension}")
            return embeddings, dimension
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise

    else:  # Default: HuggingFace all-MiniLM-L6-v2
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2"
            )
            dimension = 384
            logger.info(f"✅ Embedding: HuggingFace all-MiniLM-L6-v2 (로컬), Dimension: {dimension}")
            return embeddings, dimension
        except ImportError:
            logger.error("langchain-huggingface not installed. Run: pip install langchain-huggingface")
            raise


def get_embedding_dimension(embedding_model_name: str = None) -> int:
    """
    임베딩 모델 차원 수만 반환 (모델 로드 없이)
    벡터 인덱스 생성 시 사용
    """
    if embedding_model_name is None:
        embedding_model_name = os.getenv("LAW_EMBEDDING_MODEL", "ko-sbert")

    dimension_map = {
        "openai": 3072,  # text-embedding-3-large
        "openai-small": 1536,  # text-embedding-3-small
        "ko-sbert": 768,
        "all-MiniLM-L6-v2": 384
    }

    return dimension_map.get(embedding_model_name, 768)
