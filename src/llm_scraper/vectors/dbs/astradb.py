"""Concrete adapter for AstraDB vector database."""
import logging
from typing import Any, Dict, List, Set

from astrapy import DataAPIClient
from astrapy.data.collection import Collection

from llm_scraper.settings import settings
from llm_scraper.vectors.abc import VectorDBAdapter

log = logging.getLogger(__name__)


class AstraDBAdapter(VectorDBAdapter):
    """
    Vector database adapter for AstraDB.
    """

    def __init__(self, **kwargs: Any):
        self._client = DataAPIClient(token=settings.ASTRA_DB_APPLICATION_TOKEN)
        self._db = self._client.get_database(api_endpoint=settings.ASTRA_DB_API_ENDPOINT)
        self.collection: Collection | None = None
        log.info("AstraDBAdapter initialized.")

    def initialize(
        self, collection_name: str, embedding_dimension: int, metric: str = "cosine"
    ):
        """
        Creates or retrieves an AstraDB collection.
        """
        try:
            self.collection = self._db.create_collection(
                collection_name, dimension=embedding_dimension, metric=metric
            )
            log.info(
                f"AstraDB collection '{collection_name}' created/retrieved successfully."
            )
        except Exception as e:
            log.error(f"Failed to initialize AstraDB collection: {e}", exc_info=True)
            raise

    def upsert(self, documents: List[Dict[str, Any]]):
        """
        Inserts a batch of documents into the AstraDB collection.
        """
        if not self.collection:
            raise ConnectionError("AstraDB collection is not initialized.")
        if not documents:
            return

        try:
            result = self.collection.insert_many(documents)
            log.info(
                f"Successfully inserted {len(result.inserted_ids)} documents into AstraDB."
            )
        except Exception as e:
            log.error(f"Failed to insert documents to AstraDB: {e}", exc_info=True)
            raise

    def search(
        self, vector: List[float], limit: int, fields: Set[str]
    ) -> List[Dict[str, Any]]:
        """
        Performs a vector similarity search in AstraDB.
        """
        if not self.collection:
            raise ConnectionError("AstraDB collection is not initialized.")

        try:
            results = self.collection.vector_find(
                vector=vector,
                limit=limit,
                fields=fields,
            )
            log.info(f"Found {len(results)} results in AstraDB.")
            return results
        except Exception as e:
            log.error(f"Failed to search in AstraDB: {e}", exc_info=True)
            raise

    def get(self, id: str) -> Dict[str, Any] | None:
        """
        Retrieves a single document by its ID from AstraDB.
        """
        if not self.collection:
            raise ConnectionError("AstraDB collection is not initialized.")
        return self.collection.find_one({"_id": id})

    def count(self) -> int:
        """
        Counts the total number of documents in the AstraDB collection.
        """
        if not self.collection:
            raise ConnectionError("AstraDB collection is not initialized.")
        return self.collection.count_documents({})

    def delete_one(self, id: str) -> int:
        """
        Deletes a single document by its ID from AstraDB.
        """
        if not self.collection:
            raise ConnectionError("AstraDB collection is not initialized.")
        result = self.collection.delete_one({"_id": id})
        return result.deleted_count

    def delete_many(self, ids: List[str]) -> int:
        """
        Deletes multiple documents by their IDs from AstraDB.
        """
        if not self.collection:
            raise ConnectionError("AstraDB collection is not initialized.")
        if not ids:
            return 0
        result = self.collection.delete_many({"_id": {"$in": ids}})
        return result.deleted_count
