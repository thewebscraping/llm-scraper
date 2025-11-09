# Testing Guide

This project has two types of tests:

## 1. Unit Tests (Mocked)

Unit tests use mocked dependencies and don't require API credentials. They run fast and are ideal for CI/CD.

**Run unit tests only:**
```bash
pytest tests/test_vectors.py -v
```

**Run all unit tests (excluding integration tests):**
```bash
pytest tests/ -v -m "not integration"
```

## 2. Integration Tests (Real Environment)

Integration tests connect to real APIs (OpenAI and AstraDB) and require valid credentials in your `.env` file.

**Required environment variables:**
```env
OPENAI_API_KEY=sk-...
ASTRA_DB_APPLICATION_TOKEN=AstraCS:...
ASTRA_DB_API_ENDPOINT=https://...
ASTRA_DB_COLLECTION_NAME=your_collection_name
```

**Run integration tests:**
```bash
pytest tests/test_vectors_integration.py -v
```

**Run ALL tests (unit + integration):**
```bash
pytest tests/ -v
```

## Test Coverage

**Run tests with coverage:**
```bash
pytest tests/ --cov=src/llm_scraper --cov-report=html
```

Open `htmlcov/index.html` to view the coverage report.

## CI/CD Configuration

For CI/CD pipelines, you should run only unit tests by default:

```bash
pytest tests/ -v -m "not integration"
```

Integration tests can be run separately in a dedicated pipeline that has access to API credentials.

## Test Structure

```
tests/
├── test_articles.py           # Unit tests for article parsing
├── test_xpath_selector.py     # Unit tests for XPath selector
├── test_vectors.py            # Unit tests for vector store (mocked)
└── test_vectors_integration.py # Integration tests (real APIs)
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

### Integration Test Example
```python
import pytest

@pytest.mark.integration
def test_real_api(vector_engine):
    # Your test code using real APIs
    pass
```
