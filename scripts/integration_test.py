"""
Integration tests for the vector store with real AstraDB and OpenAI connections.

This script runs manual integration tests against real APIs.
These tests require valid API credentials in your .env file:
- OPENAI_API_KEY
- ASTRA_DB_APPLICATION_TOKEN
- ASTRA_DB_API_ENDPOINT
- ASTRA_DB_COLLECTION_NAME

To run:
    python scripts/integration_test.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_scraper.vectors import (
    VectorStoreEngine,
    Document,
    UpsertRequest,
    SearchRequest,
)
from llm_scraper.vectors.embeddings.openai import OpenAIEmbeddingAdapter
from llm_scraper.vectors.dbs.astradb import AstraDBAdapter
from llm_scraper.settings import settings


def check_credentials():
    """Check if required credentials are set."""
    missing = []
    if not settings.OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not settings.ASTRA_DB_APPLICATION_TOKEN:
        missing.append("ASTRA_DB_APPLICATION_TOKEN")
    if not settings.ASTRA_DB_API_ENDPOINT:
        missing.append("ASTRA_DB_API_ENDPOINT")
    if not settings.ASTRA_DB_COLLECTION_NAME:
        missing.append("ASTRA_DB_COLLECTION_NAME")
    
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    print("✓ All required credentials are set")


def get_vector_engine():
    """Create a VectorStoreEngine instance."""
    return VectorStoreEngine(
        embedding_adapter=OpenAIEmbeddingAdapter(),
        db_adapter=AstraDBAdapter()
    )


def test_upsert_and_search(vector_engine):
    """
    Test: Insert a real document and search for it.
    """
    print("\n" + "="*60)
    print("TEST 1: Upsert and Search")
    print("="*60)
    
    # Create a test document with a unique ID
    test_doc = Document(
        id="integration-test-doc-1",
        text="This is a test document for integration testing of the vector store.",
        metadata={"test": True, "category": "integration"}
    )
    
    # Upsert the document
    upsert_request = UpsertRequest(documents=[test_doc])
    vector_engine.upsert(upsert_request)
    print("✓ Document upserted")
    
    # Search for the document
    search_request = SearchRequest(
        query="integration testing vector store",
        limit=5
    )
    results = vector_engine.search(search_request)
    
    # Verify we got results
    assert len(results) > 0, "No search results returned"
    print(f"✓ Search returned {len(results)} results")
    print(f"  Top result: {results[0]['_id']}")
    
    # Check if our test document is in the results
    result_ids = [r.get("_id") for r in results]
    assert "integration-test-doc-1" in result_ids, \
        f"Expected test document not found. Results: {result_ids}"
    print("✓ Test document found in search results")


def test_batch_upsert(vector_engine):
    """
    Test: Insert multiple documents at once.
    """
    print("\n" + "="*60)
    print("TEST 2: Batch Upsert")
    print("="*60)
    
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
    print(f"✓ Batch upserted {len(test_docs)} documents")
    
    # Search for batch documents
    search_request = SearchRequest(
        query="batch test document",
        limit=10
    )
    results = vector_engine.search(search_request)
    
    # Verify we got results
    assert len(results) > 0, "No search results returned"
    print(f"✓ Batch search returned {len(results)} results")


def test_get_document(vector_engine):
    """
    Test: Insert and retrieve a specific document by ID.
    """
    print("\n" + "="*60)
    print("TEST 3: Get Document by ID")
    print("="*60)
    
    # Create a test document
    test_doc = Document(
        id="integration-test-get-doc",
        text="This document will be retrieved by ID.",
        metadata={"test": True, "operation": "get"}
    )
    
    # Upsert the document
    upsert_request = UpsertRequest(documents=[test_doc])
    vector_engine.upsert(upsert_request)
    print("✓ Document upserted")
    
    # Get the document by ID
    result = vector_engine.db_adapter.get("integration-test-get-doc")
    
    # Verify the document
    assert result is not None, "Document not found"
    assert result["_id"] == "integration-test-get-doc", "Wrong document ID"
    assert result["text"] == "This document will be retrieved by ID.", "Wrong text"
    print(f"✓ Retrieved document: {result['_id']}")


def test_count_documents(vector_engine):
    """
    Test: Count total documents in the collection.
    """
    print("\n" + "="*60)
    print("TEST 4: Count Documents")
    print("="*60)
    
    count = vector_engine.db_adapter.count()
    
    # Should have at least the test documents we inserted
    assert count >= 0, "Invalid count"
    print(f"✓ Total documents in collection: {count}")


def test_delete_document(vector_engine):
    """
    Test: Insert and delete a document.
    """
    print("\n" + "="*60)
    print("TEST 5: Delete Document")
    print("="*60)
    
    # Create a test document
    test_doc = Document(
        id="integration-test-delete-doc",
        text="This document will be deleted.",
        metadata={"test": True, "operation": "delete"}
    )
    
    # Upsert the document
    upsert_request = UpsertRequest(documents=[test_doc])
    vector_engine.upsert(upsert_request)
    print("✓ Document upserted")
    
    # Verify it exists
    result = vector_engine.db_adapter.get("integration-test-delete-doc")
    assert result is not None, "Document not found after upsert"
    print("✓ Document exists")
    
    # Delete the document
    deleted_count = vector_engine.db_adapter.delete_one("integration-test-delete-doc")
    assert deleted_count == 1, f"Expected 1 deletion, got {deleted_count}"
    print("✓ Document deleted")
    
    # Verify it's deleted
    result = vector_engine.db_adapter.get("integration-test-delete-doc")
    assert result is None, "Document still exists after deletion"
    print("✓ Document no longer exists")


def test_semantic_search(vector_engine):
    """
    Test: Semantic search quality with various queries.
    """
    print("\n" + "="*60)
    print("TEST 6: Semantic Search Quality")
    print("="*60)
    
    # Create diverse test documents
    test_docs = [
        Document(
            id="integration-search-python",
            text="Python is a high-level programming language known for its simplicity and readability.",
            metadata={"test": True, "category": "programming", "language": "python"}
        ),
        Document(
            id="integration-search-javascript",
            text="JavaScript is the language of the web, used for both frontend and backend development.",
            metadata={"test": True, "category": "programming", "language": "javascript"}
        ),
        Document(
            id="integration-search-ml",
            text="Machine learning is a subset of artificial intelligence that focuses on data-driven algorithms.",
            metadata={"test": True, "category": "ai", "topic": "machine learning"}
        ),
        Document(
            id="integration-search-vectors",
            text="Vector databases are optimized for storing and searching high-dimensional vectors.",
            metadata={"test": True, "category": "database", "topic": "vectors"}
        ),
    ]
    
    # Upsert all documents
    upsert_request = UpsertRequest(documents=test_docs)
    vector_engine.upsert(upsert_request)
    print(f"✓ Upserted {len(test_docs)} diverse documents")
    
    # Test 1: Search for Python-related content
    search_request = SearchRequest(query="What is Python programming language?", limit=3)
    results = vector_engine.search(search_request)
    
    assert len(results) > 0, "No results for Python query"
    result_ids = [r.get("_id") for r in results[:2]]
    assert "integration-search-python" in result_ids, \
        f"Python document should be in top 2 results. Got: {result_ids}"
    print(f"  ✓ Python search: Top result = {results[0]['_id']}")
    
    # Test 2: Search for AI/ML content
    search_request = SearchRequest(query="artificial intelligence and machine learning", limit=3)
    results = vector_engine.search(search_request)
    
    assert len(results) > 0, "No results for AI/ML query"
    result_ids = [r.get("_id") for r in results[:2]]
    assert "integration-search-ml" in result_ids, \
        f"ML document should be in top 2 results. Got: {result_ids}"
    print(f"  ✓ AI/ML search: Top result = {results[0]['_id']}")
    
    # Test 3: Search for vector database content
    search_request = SearchRequest(query="vector database storage and retrieval", limit=3)
    results = vector_engine.search(search_request)
    
    assert len(results) > 0, "No results for vector DB query"
    assert results[0]["_id"] == "integration-search-vectors", \
        f"Vector DB document should be first result. Got: {results[0]['_id']}"
    print(f"  ✓ Vector DB search: Top result = {results[0]['_id']}")
    print("✓ All semantic search tests passed")


def test_search_with_field_filtering(vector_engine):
    """
    Test: Search with field projection.
    """
    print("\n" + "="*60)
    print("TEST 7: Search with Field Filtering")
    print("="*60)
    
    # Create a test document with multiple fields
    test_doc = Document(
        id="integration-search-fields",
        text="This document has many metadata fields for testing field filtering.",
        metadata={
            "test": True,
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
            "category": "test"
        }
    )
    
    # Upsert the document
    upsert_request = UpsertRequest(documents=[test_doc])
    vector_engine.upsert(upsert_request)
    print("✓ Document with multiple fields upserted")
    
    # Search with field filtering (only return specific fields)
    search_request = SearchRequest(
        query="metadata fields testing",
        limit=5,
        fields=["_id", "text", "category"]  # Only these fields
    )
    results = vector_engine.search(search_request)
    
    assert len(results) > 0, "No search results returned"
    
    # Find our test document in results
    test_result = None
    for result in results:
        if result.get("_id") == "integration-search-fields":
            test_result = result
            break
    
    assert test_result is not None, "Test document not found in search results"
    
    # Verify only requested fields are present
    result_fields = set(test_result.keys())
    expected_fields = {"_id", "text", "category"}
    
    assert expected_fields.issubset(result_fields), \
        f"Expected fields {expected_fields} to be in result fields {result_fields}"
    
    # Should NOT have field1, field2, field3
    unwanted_fields = {"field1", "field2", "field3"}
    assert not unwanted_fields.intersection(result_fields), \
        f"Unwanted fields {unwanted_fields.intersection(result_fields)} found in result"
    
    print(f"✓ Field filtering works correctly. Result fields: {result_fields}")


def cleanup_test_documents(vector_engine):
    """
    Cleanup: Remove all test documents.
    """
    print("\n" + "="*60)
    print("CLEANUP: Removing Test Documents")
    print("="*60)
    
    # List of test document IDs to clean up
    test_ids = [
        "integration-test-doc-1",
        "integration-test-get-doc",
        "integration-test-delete-doc",
        "integration-search-python",
        "integration-search-javascript",
        "integration-search-ml",
        "integration-search-vectors",
        "integration-search-fields",
    ] + [f"integration-test-batch-{i}" for i in range(5)]
    
    # Delete test documents
    try:
        deleted = vector_engine.db_adapter.delete_many(test_ids)
        print(f"✓ Deleted {deleted} test documents")
    except Exception as e:
        print(f"✗ Cleanup error: {e}")


def main():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("INTEGRATION TESTS FOR VECTOR STORE")
    print("="*60)
    
    # Check credentials
    check_credentials()
    
    # Initialize engine
    print("\nInitializing Vector Store Engine...")
    vector_engine = get_vector_engine()
    print("✓ Engine initialized")
    
    # Track test results
    tests_passed = 0
    tests_failed = 0
    
    # Run all tests
    tests = [
        test_upsert_and_search,
        test_batch_upsert,
        test_get_document,
        test_count_documents,
        test_delete_document,
        test_semantic_search,
        test_search_with_field_filtering,
    ]
    
    for test_func in tests:
        try:
            test_func(vector_engine)
            tests_passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {e}")
            tests_failed += 1
        except Exception as e:
            print(f"\n❌ TEST ERROR: {e}")
            tests_failed += 1
    
    # Cleanup
    cleanup_test_documents(vector_engine)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✓ Passed: {tests_passed}")
    print(f"✗ Failed: {tests_failed}")
    print(f"Total: {tests_passed + tests_failed}")
    
    if tests_failed == 0:
        print("\n🎉 All integration tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {tests_failed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

