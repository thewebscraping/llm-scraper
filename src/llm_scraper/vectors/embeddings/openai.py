"""Concrete adapter for OpenAI embedding models."""
import logging
from typing import List

from openai import OpenAI

from llm_scraper.settings import settings
from llm_scraper.vectors.abc import EmbeddingAdapter

log = logging.getLogger(__name__)


class OpenAIEmbeddingAdapter(EmbeddingAdapter):
    """
    Embedding adapter for OpenAI models.
    """

    # Known dimensions for OpenAI models
    _DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, model_name: str = settings.OPENAI_EMBEDDING_MODEL):
        super().__init__(model_name)
        self._client: OpenAI | None = None
        self._embedding_dimension = self._DIMENSIONS.get(model_name)
        if not self._embedding_dimension:
            raise ValueError(
                f"Unknown embedding dimension for model '{model_name}'. "
                "Please add it to the _DIMENSIONS map in the adapter."
            )
        log.info(f"OpenAIEmbeddingAdapter initialized with model '{model_name}'.")

    @property
    def client(self) -> OpenAI:
        """
        Lazily initializes and returns the OpenAI client.
        Raises ValueError if the API key is not configured.
        """
        if self._client is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY is not set. Please configure it in your .env file."
                )
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    @property
    def embedding_dimension(self) -> int:
        return self._embedding_dimension

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for a list of texts using the OpenAI API.
        """
        if not texts:
            return []
        try:
            # OpenAI API recommends replacing newlines
            texts = [text.replace("\n", " ") for text in texts]
            response = self.client.embeddings.create(input=texts, model=self.model_name)
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            log.error(f"Failed to get embeddings from OpenAI: {e}", exc_info=True)
            raise
