# Testing Guide

This project uses unit tests with mocked dependencies for automated testing.

## Unit Tests (Mocked)

Unit tests use mocked dependencies and don't require API credentials. They run fast and are ideal for CI/CD.

**Run all unit tests:**
```bash
pytest tests/ -v
```

**Run specific test file:**
```bash
pytest tests/test_vectors.py -v
```

## Test Coverage

**Run tests with coverage:**
```bash
pytest tests/ --cov=src/llm_scraper --cov-report=html
```

Open `htmlcov/index.html` to view the coverage report.

## Integration Testing (Manual)

For testing with real APIs (OpenAI and AstraDB), use the manual test scripts in the `scripts/` folder:

**Required environment variables:**
```env
OPENAI_API_KEY=sk-...
ASTRA_DB_APPLICATION_TOKEN=AstraCS:...
ASTRA_DB_API_ENDPOINT=https://...
ASTRA_DB_COLLECTION_NAME=your_collection_name
```

**Available integration test scripts:**
```bash
# Create AstraDB collection
python scripts/create_astradb_collection.py

# Run comprehensive integration tests
python scripts/integration_test.py

# Test search functionality
python scripts/test_search.py
```

## Test Structure

```
tests/
├── test_articles.py           # Unit tests for article parsing
├── test_xpath_selector.py     # Unit tests for XPath selector
└── test_vectors.py            # Unit tests for vector store (mocked)

scripts/
├── create_astradb_collection.py  # Helper to create AstraDB collection
├── integration_test.py           # Full integration test suite
└── test_search.py                # Search functionality testing
```

## Writing New Tests

### Unit Test Example
```python
from unittest.mock import patch, MagicMock

@patch("llm_scraper.vectors.embeddings.openai.OpenAI")
def test_something(mock_openai):
    # Your test code with mocked dependencies
    pass
```

### Integration Script Example
```python
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_scraper.vectors import VectorStoreEngine

def main():
    engine = VectorStoreEngine(...)
    # Your integration test code using real APIs
    pass

if __name__ == "__main__":
    main()
```
