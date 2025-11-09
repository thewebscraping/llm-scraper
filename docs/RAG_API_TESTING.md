# Testing RAG with FastAPI Server

## Important Note

The API `/scrape` endpoint is for **user scraping only** and does NOT store articles in the vector database. 

Vector storage (RAG) is handled by **system-scheduled Celery tasks** to:
- Optimize embedding API costs
- Ensure parsing accuracy with validated configs
- Prevent duplicate/low-quality content

## Quick Start

### 1. Start the FastAPI Server

```bash
python api.py
```

Server sẽ chạy tại: `http://127.0.0.1:8000`

### 2. Test RAG API (Terminal mới)

```bash
python scripts/test_rag_api.py --no-delete
```

Script này sẽ:
- ✅ Kiểm tra server có running không
- ✅ Insert test documents vào vector store
- ✅ Test `/query` endpoint với nhiều queries
- ✅ Giữ lại test data (với `--no-delete` flag)

---

## RAG System Architecture

```
User API (/scrape)                    System Tasks (Celery)
      ↓                                       ↓
Scrape articles              Schedule scraping (sitemap/RSS)
      ↓                                       ↓
Return to user                    Parse & validate articles
                                             ↓
                                  Chunk content (512 tokens)
                                             ↓
                                  Generate embeddings (OpenAI)
                                             ↓
                                  Store in AstraDB vector DB
                                  
Both can query via /query endpoint
```

---

## Manual Testing

### Option 1: Interactive API Docs (Recommended)

Mở browser: `http://127.0.0.1:8000/docs`

1. Expand `/query` endpoint
2. Click "Try it out"
3. Nhập query, ví dụ:
   ```json
   {
     "query": "What is Python?",
     "limit": 5
   }
   ```
4. Click "Execute"

### Option 2: curl

```bash
# Test query endpoint
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Python programming language?",
    "limit": 3
  }'
```

### Option 3: Python httpx

```python
import httpx

response = httpx.post(
    "http://127.0.0.1:8000/query",
    json={"query": "artificial intelligence", "limit": 5}
)

print(response.json())
```

---

## Available Endpoints (Updated)

### 1. `POST /scrape` – User scraping (NO vector storage)

Modes:
- `single_page`: Returns Article object immediately.
- `sitemap` / `rss`: Returns `{ task_id, status_endpoint }` (background Celery task). Use follow-up endpoints to page results.

Security:
If `SYSTEM_SCRAPE_SECRET` is set, bulk modes require header:
```
X-System-Key: <secret>
```

Examples:

Single page:
```bash
curl -X POST http://127.0.0.1:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "mode": "single_page"}'
```

Sitemap (background task):
```bash
curl -X POST http://127.0.0.1:8000/scrape \
  -H "Content-Type: application/json" \
  -H "X-System-Key: $SYSTEM_SCRAPE_SECRET" \
  -d '{"url": "https://example.com/sitemap.xml", "mode": "sitemap"}'
```

Response (bulk):
```json
{ "task_id": "08f...", "status_endpoint": "/tasks/08f..." }
```

### 2. `GET /tasks/{task_id}` – Task status
Returns lightweight progress info plus `article_ids` when available. Heavy content omitted.

### 3. `GET /scrapes/{task_id}` – Paginated results
Query params:
- `include`: `ids` | `compact` | `full` (full behaves like compact; body must be fetched separately)
- `offset`: >=0
- `limit`: 1..50

Compact entry fields: `id, title, source_url, domain, word_count, format`.

### 4. `GET /article/{id}` – Fetch full article body
Use IDs returned by `/scrapes/{task_id}`.

### 5. `GET /scrapes/{task_id}/urls` – Discovered URL list (paginated)
Inspect which URLs were enumerated from sitemap/RSS.

### 6. `GET /scrapes/{task_id}/stats` – Diagnostics
Returns counts and failure list for transparency.

### 7. `DELETE /scrapes/{task_id}` – Cleanup
Removes cached results, stats, and URL queue.

### 2. `/query` - RAG search

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "vector database",
    "limit": 5
  }'
```

Response:
```json
{
  "query": "vector database",
  "results": [
    {
      "_id": "doc-1",
      "text": "Vector databases store...",
      "category": "database"
    }
  ]
}
```

---

## System RAG Workflow (Celery Tasks)

Vector storage (embeddings + AstraDB) is handled ONLY by system Celery tasks; user `/scrape` calls never write to the vector store.

### How System Tasks Work

1. **Configure sites** by adding `sitemap_url` or `rss_url` to parser configs:

```json
{
  "domain": "crypto.news",
  "lang": "en",
  "sitemap_url": "https://crypto.news/sitemap-news.xml",
  "rss_url": "https://crypto.news/feed",
  ...
}
```

2. **Celery Beat automatically schedules**:
   - Sitemap scraping: Every 6 hours
   - RSS scraping: Every 15 minutes

3. **Worker processes**:
   - Scrape → Parse → Chunk → Embed → Store in vector DB

### Manual Trigger (Development)

You can manually trigger a system ingest task (stores chunks in vector DB):

```python
from worker import scrape_site_for_rag

# Queue a task
task = scrape_site_for_rag.delay(
    url="https://crypto.news/sitemap-news.xml",
    mode="sitemap"
)
print(f"Task ID: {task.id}")
```

---

## Complete RAG Workflow

### 1. Scrape and Store (System Only)

System tasks automatically scrape configured sites and store in vector DB.

### 2. Query the Data (Anyone)

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "your search query",
    "limit": 5
  }'
```

---

## Requirements

### Environment Variables (.env)

```env
# Core RAG/vector
OPENAI_API_KEY=sk-...
ASTRA_DB_APPLICATION_TOKEN=AstraCS:...
ASTRA_DB_API_ENDPOINT=https://...
ASTRA_DB_COLLECTION_NAME=llm_scraper_rag

# Celery/Redis
REDIS_URL=redis://localhost:6379/0

# Bulk scraping control
SYSTEM_SCRAPE_SECRET=super-secret-value
SCRAPE_RESULT_TTL_DAYS=7
SCRAPE_RESULT_MAX_FULL=1000
MAX_CONCURRENT_SCRAPES=8
SCRAPE_TIMEOUT_SECONDS=20

# Hashing (optional upgrade path)
LLM_SCRAPER_HASH_ALGO=md5
LLM_SCRAPER_HASH_SECRET= # required if using hmac-sha256
```

### Services

1. **FastAPI Server** (required for API):
   ```bash
   python api.py
   ```

2. **Redis** (required for Celery):
   ```bash
   redis-server
   # or with Docker
   docker run -d -p 6379:6379 redis
   ```

3. **Celery Worker + Beat** (required for system RAG tasks):
   ```bash
   celery -A celery_app worker --beat --loglevel=info --pool=solo
   ```

---

## Troubleshooting

### Server not starting?

```bash
# Check if port 8000 is in use
lsof -i :8000

# Use different port
uvicorn api:app --port 8001
```

### "Vector store not configured"?

Kiểm tra `.env` file có đầy đủ credentials:
- `OPENAI_API_KEY`
- `ASTRA_DB_APPLICATION_TOKEN`
- `ASTRA_DB_API_ENDPOINT`
- `ASTRA_DB_COLLECTION_NAME`

### Collection doesn't exist?

```bash
python scripts/create_astradb_collection.py
```

---

## Development Tips

### Hot Reload

```bash
# Server tự động reload khi code thay đổi
python api.py
# hoặc
uvicorn api:app --reload
```

### View Logs

Server logs xuất hiện trực tiếp trong terminal khi chạy `python api.py`

### Test với Postman

Import vào Postman:
- URL: `http://127.0.0.1:8000/query`
- Method: `POST`
- Body (JSON):
  ```json
  { "query": "test query", "limit": 5 }

### Quick Bulk Scrape Flow (Sitemap/RSS)
1. POST /scrape (mode=sitemap|rss, include X-System-Key if required) → get task_id
2. Poll /tasks/{task_id} until status SUCCESS (optional)
3. Page IDs via /scrapes/{task_id}?include=ids&limit=50
4. Fetch metadata pages via include=compact if needed
5. Fetch bodies per article via /article/{id}
6. Inspect diagnostics via /scrapes/{task_id}/stats
7. Cleanup when done: DELETE /scrapes/{task_id}

This keeps payloads lean and avoids transferring large HTML/Markdown blobs unnecessarily.
  ```
