"""Placeholder for Gemini Embedding Adapter."""
import logging
from typing import List

from llm_scraper.vectors.abc import EmbeddingAdapter

log = logging.getLogger(__name__)


class GeminiEmbeddingAdapter(EmbeddingAdapter):
    """
    (Placeholder) Embedding adapter for Google Gemini models.
    """

    def __init__(self, model_name: str, **kwargs):
        super().__init__(model_name)
        log.warning(
            "GeminiEmbeddingAdapter is a placeholder and not yet implemented."
        )
        # Example: self._client = GoogleGenerativeAI(api_key=...)

    @property
    def embedding_dimension(self) -> int:
        # This would depend on the specific Gemini model
        log.warning("Returning a placeholder dimension for Gemini model.")
        return 768  # Example dimension for a base model

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        log.error("GeminiEmbeddingAdapter.get_embeddings is not implemented.")
        raise NotImplementedError(
            "This adapter is a placeholder. "
            "You need to implement the get_embeddings method using the Gemini API."
        )
        # Example implementation:
        # response = self._client.embed_content(model=self.model_name, content=texts)
        # return response['embedding']
