# RAG Workflow Architecture

## Overview

This system separates **user scraping** from **vector storage** to optimize costs and ensure quality.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER LAYER                            │
├─────────────────────────────────────────────────────────────┤
│  FastAPI /scrape endpoint                                    │
│  → single_page: Sync, returns Article                       │
│  → sitemap/rss: Async (Celery), returns task_id            │
│  → Check /tasks/{task_id} for results                       │
│  → NO vector storage                                        │
└─────────────────────────────────────────────────────────────┘
                             ↓
              (User gets articles via Celery task)

┌─────────────────────────────────────────────────────────────┐
│                       SYSTEM LAYER                           │
├─────────────────────────────────────────────────────────────┤
│  Celery Beat (Scheduler)                                    │
│  → Schedules scraping based on parser configs               │
│  → Sitemap: Every 6 hours                                   │
│  → RSS: Every 15 minutes                                    │
│                                                              │
│  Celery Worker (System Task: scrape_site_for_rag)          │
│  → Scrapes configured sites                                 │
│  → Validates with domain-specific parsers                   │
│  → Chunks content (512 tokens, 50 overlap)                  │
│  → Generates embeddings (OpenAI)                            │
│  → Stores in AstraDB vector database                        │
└─────────────────────────────────────────────────────────────┘
                             ↓
                    (Vector DB populated)

┌─────────────────────────────────────────────────────────────┐
│                       QUERY LAYER                            │
├─────────────────────────────────────────────────────────────┤
│  FastAPI /query endpoint                                     │
│  → Searches vector database                                 │
│  → Returns relevant documents                               │
│  → Available to both users and system                       │
└─────────────────────────────────────────────────────────────┘
```

## Workflow Details

### 1. User Scraping (No RAG)

**Purpose**: Allow users to extract article content on-demand

**Endpoint**: `POST /scrape`

**Modes**:
- `single_page`: Scrape one article (sync, immediate response)
- `sitemap`: Scrape all articles from sitemap (async via Celery)
- `rss`: Scrape all articles from RSS feed (async via Celery)

**Celery Task**: `scrape_for_user` (does NOT store in vector DB)

**Output**: 
- `single_page`: Article object
- `sitemap`/`rss`: `{"task_id": "...", "status_endpoint": "/tasks/..."}`

**Check Status**: `GET /tasks/{task_id}`

**Cost**: Only HTML fetching + parsing (no embeddings)

**Example (Single Page)**:
```bash
curl -X POST http://127.0.0.1:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://crypto.news/some-article/",
    "mode": "single_page"
  }'
```

**Example (Sitemap - Async)**:
```bash
# Start scraping
curl -X POST http://127.0.0.1:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://crypto.news/sitemap-news.xml",
    "mode": "sitemap"
  }'

# Response: {"task_id": "abc-123", "status_endpoint": "/tasks/abc-123"}

# Check status
curl http://127.0.0.1:8000/tasks/abc-123
```

### 2. System RAG (Background)

**Purpose**: Populate vector database with high-quality, validated content

**Trigger**: Automatic via Celery Beat scheduler

**Celery Task**: `scrape_site_for_rag` (DOES store in vector DB)

**Configuration**: Add to parser config files:
```json
{
  "domain": "crypto.news",
  "sitemap_url": "https://crypto.news/sitemap-news.xml",
  "rss_url": "https://crypto.news/feed",
  ...
}
```

**Process**:
1. Celery Beat schedules task based on config
2. Worker scrapes using validated parser config
3. Content is chunked (512 tokens, 50 token overlap)
4. OpenAI generates embeddings
5. Stored in AstraDB with metadata

**Schedule**:
- Sitemap: `crontab(hour="*/6")` - Every 6 hours
- RSS: `crontab(minute="*/15")` - Every 15 minutes

**Cost Optimization**:
- Only configured sites (avoid random URLs)
- Validated parsers (ensure quality)
- Batch processing (20 articles/batch)
- Deduplication via article IDs

**Two Separate Celery Tasks**:
- `scrape_for_user`: User requests, NO vector storage
- `scrape_site_for_rag`: System scheduled, WITH vector storage

### 3. Querying RAG

**Purpose**: Search vector database for relevant content

**Endpoint**: `POST /query`

**Available to**: Both users and system

**Example**:
```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is blockchain technology?",
    "limit": 5
  }'
```

## Why This Architecture?

### Separation of Concerns

1. **User Scraping**: Fast, on-demand, no storage costs
2. **System RAG**: Controlled, validated, optimized for quality

### Cost Control

- User scraping doesn't trigger expensive embedding operations
- Only system-selected, validated content enters vector DB
- Prevents storage of duplicate/low-quality content

### Quality Assurance

- System tasks use validated parser configs
- Manual review of configs before scheduling
- Consistent chunking and metadata

### Flexibility

- Users can still scrape any URL
- System maintains curated knowledge base
- Both can query the same vector DB

## Configuration

### Enable RAG for a Domain

Edit parser config file (e.g., `configs/en/c/crypto.news.json`):

```json
{
  "domain": "crypto.news",
  "lang": "en",
  "type": "article",
  "sitemap_url": "https://crypto.news/sitemap-news.xml",
  "rss_url": "https://crypto.news/feed",
  ...
}
```

Restart Celery worker to pick up changes:
```bash
celery -A celery_app worker --beat --loglevel=info --pool=solo
```

### View Scheduled Tasks

Check Celery Beat logs:
```
[2025-11-09 16:00:00] Scheduled sitemap task for 'crypto.news' to run every 6 hours.
[2025-11-09 16:00:00] Scheduled RSS task for 'crypto.news' to run every 15 minutes.
```

### Monitor Processing

Check worker logs:
```
[2025-11-09 16:15:00] Starting SYSTEM scrape for URL: https://crypto.news/sitemap-news.xml
[2025-11-09 16:15:30] Processing batch 1 with 20 articles.
[2025-11-09 16:16:00] Completed scrape. Processed 150 articles and 450 chunks.
```

## Running the System

### Development (3 terminals)

```bash
# Terminal 1: FastAPI
python api.py

# Terminal 2: Redis
redis-server

# Terminal 3: Celery Worker + Beat
celery -A celery_app worker --beat --loglevel=info --pool=solo
```

### Production (Docker)

```bash
docker-compose up --build
```

Services:
- `api`: FastAPI server
- `worker`: Celery worker
- `beat`: Celery beat scheduler
- `redis`: Message broker

## Testing

### Test User Scraping
```bash
curl -X POST http://127.0.0.1:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://crypto.news/article/", "mode": "single_page"}'
```

### Test RAG Query
```bash
# Insert test data first
python scripts/test_rag_api.py --no-delete

# Then query
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is FastAPI?", "limit": 5}'
```

### Manual Trigger System Task (Dev only)
```python
from worker import scrape_site_for_rag

task = scrape_site_for_rag.delay(
    url="https://crypto.news/sitemap-news.xml",
    mode="sitemap"
)
print(f"Task ID: {task.id}")
```
