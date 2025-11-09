"""
Script to test RAG functionality via FastAPI server.

This script:
1. Starts the FastAPI server
2. Inserts some test documents into the vector store
3. Tests the /query endpoint with various queries
4. Cleans up test data

Usage:
    # Terminal 1: Start server
    python api.py
    
    # Terminal 2: Run this test script
    python scripts/test_rag_api.py
"""
import sys
import time
from pathlib import Path

import httpx

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_scraper.vectors import VectorStoreEngine, Document, UpsertRequest
from llm_scraper.vectors.embeddings.openai import OpenAIEmbeddingAdapter
from llm_scraper.vectors.dbs.astradb import AstraDBAdapter

# API configuration
API_BASE_URL = "http://127.0.0.1:8000"
QUERY_ENDPOINT = f"{API_BASE_URL}/query"


def check_server_ready(max_retries=5, delay=2):
    """Check if FastAPI server is running."""
    print("🔍 Checking if server is running...")
    
    for attempt in range(max_retries):
        try:
            response = httpx.get(f"{API_BASE_URL}/docs")
            if response.status_code == 200:
                print("✅ Server is ready!")
                return True
        except httpx.ConnectError:
            if attempt < max_retries - 1:
                print(f"   ⏳ Server not ready, waiting {delay}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                print("❌ Server is not responding!")
                print("\n💡 Please start the server first:")
                print("   python api.py")
                return False
    
    return False


def insert_test_documents():
    """Insert test documents directly into vector store."""
    print("\n" + "="*60)
    print("INSERTING TEST DOCUMENTS")
    print("="*60)
    
    # Initialize engine
    engine = VectorStoreEngine(
        embedding_adapter=OpenAIEmbeddingAdapter(),
        db_adapter=AstraDBAdapter()
    )
    
    # Test documents about different topics
    test_docs = [
        Document(
            id="rag-test-python",
            text="Python is a high-level, interpreted programming language known for its simplicity and readability. It's widely used in web development, data science, and automation.",
            metadata={"category": "programming", "language": "python", "test": "rag"}
        ),
        Document(
            id="rag-test-javascript",
            text="JavaScript is a versatile programming language primarily used for web development. It powers interactive websites and runs on both browsers and servers via Node.js.",
            metadata={"category": "programming", "language": "javascript", "test": "rag"}
        ),
        Document(
            id="rag-test-ai",
            text="Artificial Intelligence (AI) is the simulation of human intelligence by machines. Machine learning and deep learning are key subfields that enable computers to learn from data.",
            metadata={"category": "ai", "topic": "machine learning", "test": "rag"}
        ),
        Document(
            id="rag-test-database",
            text="Vector databases store and retrieve high-dimensional vectors efficiently. They are essential for similarity search, semantic search, and AI applications like RAG systems.",
            metadata={"category": "database", "topic": "vectors", "test": "rag"}
        ),
        Document(
            id="rag-test-fastapi",
            text="FastAPI is a modern, fast web framework for building APIs with Python. It features automatic documentation, type checking, and high performance comparable to Node.js.",
            metadata={"category": "framework", "language": "python", "test": "rag"}
        ),
    ]
    
    # Insert documents
    upsert_request = UpsertRequest(documents=test_docs)
    result = engine.upsert(upsert_request)
    
    print(f"✅ Inserted {result['count']} test documents into vector store")
    
    return test_docs


def test_query_endpoint(query: str, limit: int = 3):
    """Test the /query endpoint."""
    print(f"\n📌 Query: '{query}' (limit={limit})")
    
    try:
        response = httpx.post(
            QUERY_ENDPOINT,
            json={"query": query, "limit": limit},
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data["results"]
            
            print(f"   ✅ Status: {response.status_code}")
            print(f"   📊 Found {len(results)} results:")
            
            for i, result in enumerate(results, 1):
                doc_id = result.get("_id", "N/A")
                text_preview = result.get("text", "")[:80] + "..."
                category = result.get("category", "N/A")
                print(f"      {i}. [{doc_id}]")
                print(f"         Category: {category}")
                print(f"         Text: {text_preview}")
            
            return results
        else:
            print(f"   ❌ Status: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
            
    except httpx.RequestError as e:
        print(f"   ❌ Request failed: {e}")
        return None


def cleanup_test_documents():
    """Remove test documents from vector store."""
    print("\n" + "="*60)
    print("CLEANUP: Removing Test Documents")
    print("="*60)
    
    try:
        engine = VectorStoreEngine(
            embedding_adapter=OpenAIEmbeddingAdapter(),
            db_adapter=AstraDBAdapter()
        )
        
        test_ids = [
            "rag-test-python",
            "rag-test-javascript",
            "rag-test-ai",
            "rag-test-database",
            "rag-test-fastapi",
        ]
        
        deleted = engine.db_adapter.delete_many(test_ids)
        print(f"✅ Deleted {deleted} test documents")
        
    except Exception as e:
        print(f"❌ Cleanup error: {e}")


def main():
    """Main test flow."""
    print("="*60)
    print("RAG API TESTING SCRIPT")
    print("="*60)
    
    # Check if server is running
    if not check_server_ready():
        return
    
    import argparse
    parser = argparse.ArgumentParser(description="Test RAG API via FastAPI server.")
    parser.add_argument('--no-delete', action='store_true', help='Do not delete test documents after testing')
    args = parser.parse_args()

    try:
        # Insert test documents
        insert_test_documents()

        # Run test queries
        print("\n" + "="*60)
        print("TESTING /query ENDPOINT")
        print("="*60)

        test_queries = [
            ("What is Python programming language?", 3),
            ("Tell me about artificial intelligence and machine learning", 3),
            ("How do vector databases work?", 2),
            ("What is FastAPI?", 2),
            ("web development with JavaScript", 3),
        ]

        passed = 0
        failed = 0

        for query, limit in test_queries:
            results = test_query_endpoint(query, limit)
            if results is not None and len(results) > 0:
                passed += 1
            else:
                failed += 1

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Total: {passed + failed}")

        if failed == 0:
            print("\n🎉 All RAG API tests passed!")
        else:
            print(f"\n⚠️  {failed} test(s) failed")

    finally:
        # Cleanup only if --no-delete is not set
        if not args.no_delete:
            cleanup_test_documents()

    print("\n💡 Next steps:")
    print("   - Test with your own queries")
    print("   - Try the interactive docs: http://127.0.0.1:8000/docs")
    print("   - Use curl: curl -X POST http://127.0.0.1:8000/query -H 'Content-Type: application/json' -d '{\"query\":\"your query\"}'")


if __name__ == "__main__":
    main()
