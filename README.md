# LLM Scraper

A flexible, configuration-driven web scraper designed to extract article content and feed it into a Retrieval-Augmented Generation (RAG) pipeline.

This project uses a professional, scalable architecture with domain-specific parser configurations to accurately extract structured data from web pages.

## 📚 Documentation

**[Complete Documentation →](docs/README.md)**

- **[Selector Guide](docs/SELECTOR_GUIDE.md)** - Creating parser configurations with CSS and XPath
- **[XPath Feature Guide](docs/XPATH_FEATURE.md)** - Advanced XPath selector usage
- **[Article API](docs/API_ARTICLE.md)** - Article model reference
- Quick examples and tutorials

## Core Features

- **🎯 Dual Selector System**: Support for both CSS and XPath selectors with automatic detection
- **🧹 3-Layer Cleanup Architecture**: Global, per-field, and safety cleanup for pristine content
- **📝 Markdown Output**: Clean, structured markdown with preserved links and formatting
- **⚙️ Config-Driven Parsing**: Define how to scrape any site using simple JSON configuration files
- **🔄 Flexible Selectors**: Support for fallback chains, parent scoping, and per-selector attributes
- **📊 Rich Metadata**: Extracts OpenGraph, Schema.org, authors, dates, tags, and topics
- **🤖 RAG-Ready**:
  - Automatically chunks content with token estimation for LLM context windows.
  - Features a modular vector store engine with an adapter pattern for different databases (AstraDB) and embedding models (OpenAI).
- **✅ Production-Ready**: Pydantic v2 validation, lazy-loaded clients for robust startup, error handling, and deterministic UUIDs.

## What's New in XPath Enhancement

- **XPath Support**: Use powerful XPath expressions for precise element selection
- **Automatic Type Detection**: Mix CSS and XPath selectors - the system auto-detects
- **Attribute Extraction**: Direct attribute access via XPath (e.g., `//time[@datetime]/@datetime`)
- **3-Layer Cleanup**:
  1. Global cleanup (script, style, noscript, iframe)
  2. Per-field cleanup (ads, sponsors, related posts)
  3. Safety cleanup with preset selectors
- **Markdown Output**: HTML → Clean HTML → Markdown workflow preserves structure
- **90+ Migrated Configs**: All parser configs updated to new architecture

## Project Structure

```
.
├── Procfile              # Defines processes for Honcho (api, worker, beat)
├── api.py                # FastAPI application, the user-facing entrypoint
├── celery_app.py         # Celery application instance configuration
├── pyproject.toml        # Project metadata and dependencies
├── src/
│   └── llm_scraper/
│       ├── __init__.py
│       ├── articles.py   # Core Article data model and chunking logic
│       ├── meta.py       # Metadata extraction logic
│       ├── parsers/      # Site-specific parser configurations
│       ├── schema.py     # Pydantic models for configuration and data
│       ├── settings.py   # Application settings management (from .env)
│       ├── utils/        # Utility functions
│       └── vectors/      # Modular vector store engine and adapters
│           ├── abc.py    # Abstract base classes for adapters
│           ├── engine.py # The main VectorStoreEngine
│           ├── dbs/      # Vector database adapters (e.g., AstraDB)
│           └── embeddings/ # Embedding model adapters (e.g., OpenAI)
└── worker.py             # Celery worker and scheduler (Celery Beat) definitions
```

## Setup

1.  **Install Dependencies**: This project uses `uv` for package management.
    ```bash
    uv pip install -r requirements.txt
    ```

2.  **Environment Variables**: Create a `.env` file in the root directory and add your credentials:
    ```env
    # .env
    OPENAI_API_KEY="sk-..."
    ASTRA_DB_APPLICATION_TOKEN="AstraCS:..."
    ASTRA_DB_API_ENDPOINT="https://..."
    ASTRA_DB_COLLECTION_NAME="your_collection_name"
    REDIS_URL="redis://localhost:6379/0"
    ```

3.  **Run Redis**: Ensure you have a Redis server running locally. You can use Docker for this:
    ```bash
    docker run -d -p 6379:6379 redis
    ```

## Quick Start Examples

### Test a Parser Config

Validate article extraction from a fixture:

```bash
# Test with markdown output (default)
python scripts/validate_article_fixture.py fixtures/en/c/cryptoslate.com.json

# Test with HTML output
python scripts/validate_article_fixture.py fixtures/en/c/crypto.news.json --format html
```

### Create a Fixture from URL

Fetch HTML and create a test fixture:

```bash
python scripts/fetch_and_create_fixture.py https://crypto.news/article-slug/
```

### Batch Create Fixtures

Process multiple URLs at once:

```bash
# From a file (one URL per line)
python scripts/batch_create_fixtures.py urls.txt

# From command line
python scripts/batch_create_fixtures.py --urls https://site1.com/article https://site2.com/article
```

### Debug Site Structure

Analyze HTML structure using preset selectors:

```bash
python scripts/debug_site_structure.py fixtures/en/c/domain.json
```

## How to Run

You can run the system in two ways: locally using `honcho` or with Docker.

### 1. Running with Docker (Recommended)

This is the easiest way to run the entire system, including the Redis database.

**Prerequisites**:
- Docker and Docker Compose installed.
- A `.env` file with your credentials (see Setup section).

**To start the entire system, run:**
```bash
docker-compose up --build
```
This command will:
1.  Build the Docker image for the application based on the `Dockerfile`.
2.  Start containers for the `api`, `worker`, `beat`, and `redis` services.
3.  Display all logs in your terminal.

To stop the services, press `Ctrl+C`.

### 2. Running Locally with Honcho

Use this method if you prefer not to use Docker.

**Prerequisites**:
- Python and `uv` installed.
- A running Redis server (e.g., `docker run -d -p 6379:6379 redis`).
- Dependencies installed (`uv pip install -r requirements.txt`).
- A `.env` file with your credentials.

**To start the entire system, run:**
```bash
honcho start
```

## API Usage

The API provides two main functions:
1. Scraping: Extract article content from URLs (single pages, sitemaps, or RSS feeds)
2. Querying: Search the RAG vector database

Notes:
- User scraping via API does NOT automatically store articles in the vector database. Vector storage is handled by system-scheduled tasks to optimize cost and ensure parsing accuracy.
- Bulk scraping modes (sitemap, rss) are protected by a system secret header when configured.

### Endpoints

#### POST /scrape
Scrape content based on the specified mode.

- single_page: Scrapes a single article URL and returns the Article object inline.
- sitemap or rss: Starts a background task and returns a task_id (results are retrieved via the /tasks and /scrapes endpoints).

Headers (required for sitemap/rss when SYSTEM_SCRAPE_SECRET is set):
- X-System-Key: <your system secret>

Request Body:
- url: string (article/sitemap/feed URL)
- mode: one of single_page | sitemap | rss
- output_format: markdown | html (default markdown)

Responses:
- single_page: Article object (includes content). 
- sitemap/rss: { "task_id": "...", "status_endpoint": "/tasks/{id}" }

#### GET /tasks/{task_id}
Check background task status. Heavy payloads are stripped.

Response fields:
- task_id, status (PENDING|PROGRESS|SUCCESS|FAILURE), result (lightweight meta), article_ids (if any)

#### GET /scrapes/{task_id}
Fetch paginated scrape results for a task.

Query params:
- include: ids | compact | full (full currently behaves like compact to force fetching bodies via /article/{id})
- offset: integer >= 0
- limit: integer 1..50 (enforced)

Responses:
- include=ids: { ids: [id, ...], total, offset, limit, next_offset }
- include=compact|full: { articles: [{ id, title, source_url, domain, word_count, format }], total, offset, limit, next_offset, note }

#### GET /article/{id}
Fetch a single persisted article including body. Use this to retrieve content by id listed in /scrapes results.

#### GET /scrapes/{task_id}/urls
Paginated list of discovered URLs for the task (helpful for large sitemap/rss runs).

Query params: offset, limit (1..50)

#### GET /scrapes/{task_id}/stats
Diagnostic stats for the task: totals, success/failure counts, and failed URL list.

#### DELETE /scrapes/{task_id}
Delete cached results, stats, and the per-task URL queue.

#### `POST /query`
Perform a similarity search on the vectorized data in AstraDB.

**Request Body:**
```json
{
  "query": "What is blockchain?",
  "limit": 5
}
```

## Parser Configuration

Parser configs support both CSS and XPath selectors with automatic type detection:

```json
{
  "domain": "example.com",
  "lang": "en",
  "type": "article",
  "cleanup": ["script", "style", "noscript", "iframe"],
  "title": {
    "selector": ["h1.article-title", "h1"]
  },
  "content": {
    "selector": [
      "//article[@id='main']/div[3]",
      ".article-content",
      "article"
    ],
    "cleanup": [
      ".ads",
      ".related-posts",
      "[class*='sponsor']"
    ]
  },
  "authors": {
    "selector": ["//a[@rel='author']", ".author-name"],
    "all": true
  },
  "date_published": {
    "selector": ["//time[@datetime]/@datetime", "time[datetime]"],
    "attribute": "datetime"
  },
  "tags": {
    "selector": ["//a[@rel='tag']", ".tags a"],
    "all": true
  }
}
```

**Key Features:**
- **Selector fallback chains**: Try XPath first, fall back to CSS
- **Global cleanup**: Remove script/style/iframe from entire page
- **Per-field cleanup**: Remove ads/sponsors from specific fields
- **Attribute extraction**: Get attribute values directly with XPath `@attr` syntax
- **Multi-value extraction**: Use `"all": true` to extract all matches

See [XPATH_FEATURE.md](XPATH_FEATURE.md) for detailed examples and best practices.

## Environment Variables

Core RAG/vector:
- OPENAI_API_KEY
- ASTRA_DB_APPLICATION_TOKEN
- ASTRA_DB_API_ENDPOINT
- ASTRA_DB_COLLECTION_NAME

Async/background & caching:
- REDIS_URL: Redis broker for Celery
- SCRAPE_RESULT_TTL_DAYS: Days to keep cached results (default 7)
- SCRAPE_RESULT_MAX_FULL: Max articles to store as a full list per task (beyond this, only per-article docs are saved)
- MAX_CONCURRENT_SCRAPES: Limit concurrent fetches in bulk modes (default 8)
- SCRAPE_TIMEOUT_SECONDS: Per-request timeout (default 20)

Security:
- SYSTEM_SCRAPE_SECRET: If set, sitemap/rss modes require X-System-Key header to match

Hashing (advanced):
- LLM_SCRAPER_HASH_ALGO: md5 | sha1 | sha256 | hmac-sha256 (default md5 for backward compatibility)
- LLM_SCRAPER_HASH_SECRET: required when using hmac-sha256
