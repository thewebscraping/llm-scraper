import os
import pytest
from unittest.mock import patch, MagicMock

from llm_scraper.vectors import (
    VectorStoreEngine,
    Document,
    UpsertRequest,
    SearchRequest,
)
from llm_scraper.vectors.embeddings.openai import OpenAIEmbeddingAdapter
from llm_scraper.vectors.dbs.astradb import AstraDBAdapter


def test_engine_initialization():
    """Tests that the VectorStoreEngine initializes without errors."""
    engine = VectorStoreEngine(
        embedding_adapter=OpenAIEmbeddingAdapter(), db_adapter=AstraDBAdapter()
    )
    assert engine is not None
    assert isinstance(engine.embedding_adapter, OpenAIEmbeddingAdapter)
    assert isinstance(engine.db_adapter, AstraDBAdapter)


@patch("llm_scraper.vectors.embeddings.openai.OpenAI")
@patch("llm_scraper.vectors.dbs.astradb.DataAPIClient")
def test_upsert_operation_with_mocks(mock_data_api_client, mock_openai_client):
    """Tests the full upsert flow with properly mocked external dependencies."""
    # Mock the embedding client
    mock_embedding_instance = MagicMock()
    mock_embedding_instance.embeddings.create.return_value.data = [
        MagicMock(embedding=[0.1] * 1536)
    ]
    mock_openai_client.return_value = mock_embedding_instance

    # Mock the DataAPIClient and collection
    mock_collection = MagicMock()
    mock_collection.insert_many.return_value = MagicMock(inserted_ids=["test-doc-1"])
    mock_db = MagicMock()
    mock_db.get_collection.return_value = mock_collection
    mock_data_api_client.return_value.get_database.return_value = mock_db

    # Initialize engine
    engine = VectorStoreEngine(
        embedding_adapter=OpenAIEmbeddingAdapter(), db_adapter=AstraDBAdapter()
    )

    # Create a dummy document and upsert it
    docs = [Document(id="test-doc-1", text="This is a test document.")]
    upsert_request = UpsertRequest(documents=docs)
    engine.upsert(upsert_request)

    # --- Assertions ---
    # 1. Check that clients were initialized
    assert mock_openai_client.called
    assert mock_data_api_client.called

    # 2. Check that the embedding model was called
    mock_embedding_instance.embeddings.create.assert_called_once()
    call_args = mock_embedding_instance.embeddings.create.call_args
    assert call_args.kwargs["input"] == ["This is a test document."]
    assert call_args.kwargs["model"] == "text-embedding-3-small"

    # 3. Check that insert_many was called on the collection
    mock_collection.insert_many.assert_called_once()
    insert_args = mock_collection.insert_many.call_args[0][0]
    assert len(insert_args) == 1
    assert insert_args[0]["_id"] == "test-doc-1"
    assert insert_args[0]["text"] == "This is a test document."
    assert "$vector" in insert_args[0]
    assert len(insert_args[0]["$vector"]) == 1536


@patch("llm_scraper.vectors.embeddings.openai.OpenAI")
@patch("llm_scraper.vectors.dbs.astradb.DataAPIClient")
def test_search_operation_with_mocks(mock_data_api_client, mock_openai_client):
    """Tests the full search flow with properly mocked dependencies."""
    # Mock the embedding client
    mock_embedding_instance = MagicMock()
    mock_embedding_instance.embeddings.create.return_value.data = [
        MagicMock(embedding=[0.2] * 1536)
    ]
    mock_openai_client.return_value = mock_embedding_instance

    # Mock the DataAPIClient and collection
    mock_collection = MagicMock()
    mock_collection.find.return_value = [
        {"_id": "found-doc-1", "text": "Found document.", "metadata": {}}
    ]
    mock_db = MagicMock()
    mock_db.get_collection.return_value = mock_collection
    mock_data_api_client.return_value.get_database.return_value = mock_db

    # Initialize engine
    engine = VectorStoreEngine(
        embedding_adapter=OpenAIEmbeddingAdapter(), db_adapter=AstraDBAdapter()
    )

    # Perform a search
    search_request = SearchRequest(query="test query", limit=3)
    results = engine.search(search_request)

    # --- Assertions ---
    # 1. Check embedding creation for the query
    mock_embedding_instance.embeddings.create.assert_called_once_with(
        input=["test query"], model="text-embedding-3-small"
    )

    # 2. Check that the find method was called on the collection
    mock_collection.find.assert_called_once()
    find_args = mock_collection.find.call_args.kwargs
    assert "sort" in find_args
    assert find_args["sort"] == {"$vector": [0.2] * 1536}
    assert "limit" in find_args
    assert find_args["limit"] == 3

    # 3. Check the results
    assert len(results) == 1
    assert results[0]["_id"] == "found-doc-1"

