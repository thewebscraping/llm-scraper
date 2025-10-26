from __future__ import annotations

import logging
from typing import List

from astrapy import DataAPIClient
from openai import OpenAI

from llm_scraper.settings import settings

# --- Globals ---
log = logging.getLogger(__name__)
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


class VectorStore:
    """
    A wrapper class to handle all interactions with the AstraDB vector database
    and OpenAI's embedding API.
    """

    def __init__(self):
        self.db = DataAPIClient(
            settings.ASTRA_DB_API_ENDPOINT,
            token=settings.ASTRA_DB_APPLICATION_TOKEN,
        )
        self.collection = None
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        # OpenAI's 'text-embedding-3-small' model has 1536 dimensions
        self.embedding_dimension = 1536

    def initialize_collection(self):
        """
        Connects to the database and creates the collection if it doesn't exist.
        The collection is configured for vector search with the correct dimension.
        """
        try:
            collection_name = settings.ASTRA_DB_COLLECTION_NAME
            # Create a collection with vector search enabled
            self.collection = self.db.create_collection(
                collection_name, dimension=self.embedding_dimension, metric="cosine"
            )
            log.info(f"AstraDB collection '{collection_name}' created/retrieved successfully.")
        except Exception as e:
            log.error(f"Failed to initialize AstraDB collection: {e}", exc_info=True)
            raise

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Takes a list of text strings and returns a list of embedding vectors
        from OpenAI's API.
        """
        if not texts:
            return []
        try:
            # Replace newlines to avoid issues with the API
            texts = [text.replace("\n", " ") for text in texts]
            response = openai_client.embeddings.create(input=texts, model=self.embedding_model)
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            log.error(f"Failed to get embeddings from OpenAI: {e}", exc_info=True)
            raise

    def upsert_documents(self, documents: List[dict]):
        """
        Takes a list of documents, generates embeddings for their 'text' field,
        and upserts them into the AstraDB collection.
        """
        if not self.collection:
            raise ConnectionError("AstraDB collection is not initialized. Call `initialize_collection` first.")
        if not documents:
            return

        # Extract the text content for embedding
        texts_to_embed = [doc["text"] for doc in documents]
        embeddings = self.get_embeddings(texts_to_embed)

        # Add the vector to each document
        for i, doc in enumerate(documents):
            doc["$vector"] = embeddings[i]

        try:
            # `upsert` is efficient for batch inserting/updating
            self.collection.upsert(documents)
            log.info(f"Successfully upserted {len(documents)} documents into AstraDB.")
        except Exception as e:
            log.error(f"Failed to upsert documents to AstraDB: {e}", exc_info=True)
            raise

    def search(self, query_text: str, limit: int = 5) -> List[dict]:
        """
        Performs a similarity search in the AstraDB collection.
        It takes a query string, generates its embedding, and finds the most
        similar documents.
        """
        if not self.collection:
            raise ConnectionError("AstraDB collection is not initialized. Call `initialize_collection` first.")

        # Get the embedding for the user's query
        query_embedding = self.get_embeddings([query_text])[0]

        try:
            # Perform the vector search
            results = self.collection.vector_find(
                vector=query_embedding,
                limit=limit,
                fields={"text", "title", "source_url", "domain"},  # Only return these fields
            )
            log.info(f"Found {len(results)} results in AstraDB for query: '{query_text}'")
            return results
        except Exception as e:
            log.error(f"Failed to search in AstraDB: {e}", exc_info=True)
            raise


# Create a single, reusable instance of the vector store
vector_store = VectorStore()
