"""
Shared OpenAI client for all domain agents

Provides singleton OpenAI client for embeddings and chat completions.
"""

from openai import OpenAI
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# Singleton instance
_openai_client = None


def get_openai_client() -> OpenAI:
    """
    Get the singleton OpenAI client instance

    Returns:
        OpenAI client instance
    """
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        _openai_client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized")

    return _openai_client


def generate_embedding(text: str, model: str = "text-embedding-3-large") -> list[float]:
    """
    Generate embedding for text using OpenAI

    Args:
        text: Text to embed
        model: OpenAI embedding model name

    Returns:
        Embedding vector as list of floats
    """
    client = get_openai_client()
    response = client.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding
