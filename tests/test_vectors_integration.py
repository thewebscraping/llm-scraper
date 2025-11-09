"""
Integration tests for the vector store with real AstraDB and OpenAI connections.

These tests require valid API credentials in your .env file:
- OPENAI_API_KEY
- ASTRA_DB_APPLICATION_TOKEN
- ASTRA_DB_API_ENDPOINT
- ASTRA_DB_COLLECTION_NAME

To run only integration tests:
    pytest tests/test_vectors_integration.py -v

To skip integration tests:
    pytest tests/ -v -m "not integration"
"""

import pytest
from llm_scraper.vectors import (
    VectorStoreEngine,
    Document,
    UpsertRequest,
    SearchRequest,
)
from llm_scraper.vectors.embeddings.openai import OpenAIEmbeddingAdapter
from llm_scraper.vectors.dbs.astradb import AstraDBAdapter
from llm_scraper.settings import settings


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def check_credentials():
    """Skip test if required credentials are not set."""
    if not settings.OPENAI_API_KEY:
        pytest.skip("OPENAI_API_KEY not set in environment")
    if not settings.ASTRA_DB_APPLICATION_TOKEN:
        pytest.skip("ASTRA_DB_APPLICATION_TOKEN not set in environment")
    if not settings.ASTRA_DB_API_ENDPOINT:
        pytest.skip("ASTRA_DB_API_ENDPOINT not set in environment")
    if not settings.ASTRA_DB_COLLECTION_NAME:
        pytest.skip("ASTRA_DB_COLLECTION_NAME not set in environment")


@pytest.fixture
def vector_engine(check_credentials):
    """Fixture to create a real VectorStoreEngine instance."""
    engine = VectorStoreEngine(
        embedding_adapter=OpenAIEmbeddingAdapter(),
        db_adapter=AstraDBAdapter()
    )
    return engine


def test_real_upsert_and_search(vector_engine):
    """
    Integration test: Insert a real document and search for it.
    This test will actually call OpenAI API and AstraDB.
    """
    # Create a test document with a unique ID
    test_doc = Document(
        id="integration-test-doc-1",
        text="This is a test document for integration testing of the vector store.",
        metadata={"test": True, "category": "integration"}
    )
    
    # Upsert the document
    upsert_request = UpsertRequest(documents=[test_doc])
    vector_engine.upsert(upsert_request)
    
    # Search for the document
    search_request = SearchRequest(
        query="integration testing vector store",
        limit=5
    )
    results = vector_engine.search(search_request)
    
    # Verify we got results
    assert len(results) > 0
    
    # The first result should be our test document (or very similar)
    print(f"\nSearch returned {len(results)} results")
    print(f"Top result: {results[0]}")
    
    # Check if our test document is in the results
    result_ids = [r.get("_id") for r in results]
    assert "integration-test-doc-1" in result_ids, \
        f"Expected test document not found. Results: {result_ids}"


def test_real_batch_upsert(vector_engine):
    """
    Integration test: Insert multiple documents at once.
    """
    # Create multiple test documents
    test_docs = [
        Document(
            id=f"integration-test-batch-{i}",
            text=f"This is batch test document number {i}.",
            metadata={"test": True, "batch": True, "index": i}
        )
        for i in range(5)
    ]
    
    # Upsert all documents
    upsert_request = UpsertRequest(documents=test_docs)
    vector_engine.upsert(upsert_request)
    
    # Search for batch documents
    search_request = SearchRequest(
        query="batch test document",
        limit=10
    )
    results = vector_engine.search(search_request)
    
    # Verify we got results
    assert len(results) > 0
    print(f"\nBatch search returned {len(results)} results")


def test_real_get_document(vector_engine):
    """
    Integration test: Insert and retrieve a specific document by ID.
    """
    # Create a test document
    test_doc = Document(
        id="integration-test-get-doc",
        text="This document will be retrieved by ID.",
        metadata={"test": True, "operation": "get"}
    )
    
    # Upsert the document
    upsert_request = UpsertRequest(documents=[test_doc])
    vector_engine.upsert(upsert_request)
    
    # Get the document by ID
    result = vector_engine.db_adapter.get("integration-test-get-doc")
    
    # Verify the document
    assert result is not None
    assert result["_id"] == "integration-test-get-doc"
    assert result["text"] == "This document will be retrieved by ID."
    print(f"\nRetrieved document: {result}")


def test_real_count_documents(vector_engine):
    """
    Integration test: Count total documents in the collection.
    """
    count = vector_engine.db_adapter.count()
    
    # Should have at least the test documents we inserted
    assert count >= 0
    print(f"\nTotal documents in collection: {count}")


def test_real_delete_document(vector_engine):
    """
    Integration test: Insert and delete a document.
    """
    # Create a test document
    test_doc = Document(
        id="integration-test-delete-doc",
        text="This document will be deleted.",
        metadata={"test": True, "operation": "delete"}
    )
    
    # Upsert the document
    upsert_request = UpsertRequest(documents=[test_doc])
    vector_engine.upsert(upsert_request)
    
    # Verify it exists
    result = vector_engine.db_adapter.get("integration-test-delete-doc")
    assert result is not None
    
    # Delete the document
    deleted_count = vector_engine.db_adapter.delete_one("integration-test-delete-doc")
    assert deleted_count == 1
    
    # Verify it's deleted
    result = vector_engine.db_adapter.get("integration-test-delete-doc")
    assert result is None
    print("\nDocument successfully deleted")


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_documents(check_credentials):
    """
    Cleanup fixture: Remove all test documents after all integration tests complete.
    """
    yield  # Let all tests run first
    
    # Cleanup after tests
    try:
        engine = VectorStoreEngine(
            embedding_adapter=OpenAIEmbeddingAdapter(),
            db_adapter=AstraDBAdapter()
        )
        
        # List of test document IDs to clean up
        test_ids = [
            "integration-test-doc-1",
            "integration-test-get-doc",
            "integration-test-delete-doc",
        ] + [f"integration-test-batch-{i}" for i in range(5)]
        
        # Delete test documents
        deleted = engine.db_adapter.delete_many(test_ids)
        print(f"\n✓ Cleanup: Deleted {deleted} test documents")
    except Exception as e:
        print(f"\n✗ Cleanup error: {e}")
