#!/usr/bin/env python
"""
Script to create an AstraDB collection for the vector store if it doesn't exist.

Usage:
    python scripts/create_astradb_collection.py
"""

from llm_scraper.settings import settings
from llm_scraper.vectors.dbs.astradb import AstraDBAdapter

def main():
    """Create the AstraDB collection if it doesn't exist."""
    if not settings.ASTRA_DB_APPLICATION_TOKEN:
        print("❌ Error: ASTRA_DB_APPLICATION_TOKEN not set in environment")
        return
    
    if not settings.ASTRA_DB_API_ENDPOINT:
        print("❌ Error: ASTRA_DB_API_ENDPOINT not set in environment")
        return
    
    if not settings.ASTRA_DB_COLLECTION_NAME:
        print("❌ Error: ASTRA_DB_COLLECTION_NAME not set in environment")
        return
    
    print(f"Creating/checking collection: {settings.ASTRA_DB_COLLECTION_NAME}")
    print(f"Database endpoint: {settings.ASTRA_DB_API_ENDPOINT}")
    
    adapter = AstraDBAdapter()
    
    try:
        # Initialize the collection (creates if doesn't exist)
        adapter.initialize(
            collection_name=settings.ASTRA_DB_COLLECTION_NAME,
            embedding_dimension=1536,  # OpenAI text-embedding-3-small dimension
            metric="cosine"
        )
        print(f"✅ Collection '{settings.ASTRA_DB_COLLECTION_NAME}' is ready!")
        
        # Try to count documents
        count = adapter.count()
        print(f"📊 Current document count: {count}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()
