"""Concrete adapter for AstraDB vector database."""
import logging
from typing import Any, Dict, List, Set

from astrapy import DataAPIClient
from astrapy.constants import VectorMetric
from astrapy.data.collection import Collection
from astrapy.info import CollectionDefinition, CollectionVectorOptions

from llm_scraper.settings import settings
from llm_scraper.vectors.abc import VectorDBAdapter

log = logging.getLogger(__name__)


class AstraDBAdapter(VectorDBAdapter):
    """
    Vector database adapter for AstraDB.
    """

    def __init__(self, **kwargs: Any):
        self._client: DataAPIClient | None = None
        self._db: Any | None = None
        self.collection: Collection | None = None
        log.info("AstraDBAdapter initialized.")

    @property
    def client(self) -> DataAPIClient:
        """
        Lazily initializes and returns the AstraDB DataAPIClient.
        """
        if self._client is None:
            if not settings.ASTRA_DB_APPLICATION_TOKEN:
                raise ValueError(
                    "ASTRA_DB_APPLICATION_TOKEN is not set. "
                    "Please configure it in your .env file."
                )
            self._client = DataAPIClient(token=settings.ASTRA_DB_APPLICATION_TOKEN)
        return self._client

    @property
    def db(self):
        """
        Lazily initializes and returns the AstraDB database instance.
        """
        if self._db is None:
            if not settings.ASTRA_DB_API_ENDPOINT:
                raise ValueError(
                    "ASTRA_DB_API_ENDPOINT is not set. "
                    "Please configure it in your .env file."
                )
            self._db = self.client.get_database(
                api_endpoint=settings.ASTRA_DB_API_ENDPOINT
            )
        return self._db

    def initialize(
        self, collection_name: str, embedding_dimension: int, metric: str = "cosine"
    ):
        """
        Creates or retrieves an AstraDB collection with the proper vector configuration.
        """
        try:
            # Map metric string to VectorMetric enum
            metric_map = {
                "cosine": VectorMetric.COSINE,
                "dot_product": VectorMetric.DOT_PRODUCT,
                "euclidean": VectorMetric.EUCLIDEAN,
            }
            vector_metric = metric_map.get(metric.lower(), VectorMetric.COSINE)
            
            # Try to get existing collection first
            try:
                self.collection = self.db.get_collection(collection_name)
                log.info(
                    f"AstraDB collection '{collection_name}' retrieved successfully."
                )
            except Exception:
                # Collection doesn't exist, create it
                log.info(f"Creating new collection '{collection_name}'...")
                self.collection = self.db.create_collection(
                    collection_name,
                    definition=CollectionDefinition(
                        vector=CollectionVectorOptions(
                            dimension=embedding_dimension,
                            metric=vector_metric,
                        ),
                    ),
                )
                log.info(
                    f"AstraDB collection '{collection_name}' created successfully."
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
            results = list(
                self.collection.find(
                    sort={"$vector": vector},
                    limit=limit,
                    projection={field: 1 for field in fields} if fields else {"$vector": 0},
                )
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
