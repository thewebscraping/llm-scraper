import logging
from pathlib import Path
import json
from typing import Dict, List, Literal, Union
from urllib.parse import urlparse

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Response, Header
from pydantic import BaseModel, HttpUrl

from celery_app import celery_app
from llm_scraper import GENERIC_CONFIG, Article, ParserConfig, Scraper, ScraperCache
from llm_scraper.vectors import (
    SearchRequest,
    VectorStoreEngine,
)
from llm_scraper.vectors.dbs.astradb import AstraDBAdapter
from llm_scraper.vectors.embeddings.openai import OpenAIEmbeddingAdapter
from worker import scrape_for_user
from llm_scraper.cache import ArticlesCache

# --- Globals ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scraper_api")
SHARED_CACHE = ScraperCache()
CONFIGS: Dict[str, ParserConfig] = {}
RESULTS_CACHE = ArticlesCache()

# Lazily initialize the vector store engine
_VECTOR_STORE_ENGINE: VectorStoreEngine | None = None


def get_vector_store_engine() -> VectorStoreEngine:
    """
    Initializes and returns a singleton instance of the VectorStoreEngine.
    """
    global _VECTOR_STORE_ENGINE
    if _VECTOR_STORE_ENGINE is None:
        log.info("Initializing VectorStoreEngine for the first time for API.")
        _VECTOR_STORE_ENGINE = VectorStoreEngine(
            embedding_adapter=OpenAIEmbeddingAdapter(), db_adapter=AstraDBAdapter()
        )
    return _VECTOR_STORE_ENGINE


# --- FastAPI App Initialization ---
app = FastAPI(
    title="LLM Scraper API",
    description="An API for scraping articles, powered by a flexible, config-driven engine.",
)


# --- Startup Event ---
@app.on_event("startup")
def startup_event():
    """On startup, load parser configs and initialize the connection to AstraDB."""
    from worker import load_parser_config  # Import here to avoid circular dependency issues

    config_dir = Path.cwd() / "src" / "llm_scraper" / "parsers" / "configs"
    if config_dir.is_dir():
        for config_file in config_dir.glob("*.json"):
            try:
                domain = json.load(open(config_file))["domain"]
                config = load_parser_config(domain)
                if config:
                    CONFIGS[domain] = config
                    log.info(f"Loaded config for '{domain}'")
            except (json.JSONDecodeError, KeyError):
                continue
    # The engine now handles initialization automatically upon instantiation.
    # We can add a health check here if needed.
    log.info("Vector store engine is initialized.")



# --- API Request/Response Models ---
class ScrapeRequest(BaseModel):
    url: HttpUrl
    mode: Literal["single_page", "sitemap", "rss"] = "single_page"
    output_format: Literal["markdown", "html"] = "markdown"


class TaskResponse(BaseModel):
    task_id: str
    status_endpoint: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None
    article_ids: List[str] | None = None
    # articles field intentionally omitted from status to avoid huge payloads


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


class QueryResponse(BaseModel):
    query: str
    results: List[dict]


# --- API Endpoints ---
@app.post("/scrape", response_model=Union[Article, TaskResponse])
async def scrape(request: ScrapeRequest, response: Response, x_system_key: str | None = Header(default=None, alias="X-System-Key")):
    """
    Scrapes content based on the specified mode.
    
    - **single_page**: Scrapes a single article URL and returns the Article directly.
    - **sitemap**: Triggers background task to scrape sitemap, returns task_id.
    - **rss**: Triggers background task to scrape RSS feed, returns task_id.
    
    Important: This endpoint does NOT store articles in the vector database.
    Vector storage is handled separately by scheduled system tasks.
    """
    
    # For sitemap/rss: Use Celery background task
    if request.mode in ["sitemap", "rss"]:
        # Enforce system secret for bulk modes to prevent misuse
        import os
        required = os.getenv("SYSTEM_SCRAPE_SECRET")
        if required:
            if not x_system_key or x_system_key != required:
                raise HTTPException(status_code=403, detail="Forbidden: invalid or missing system key for bulk scrape mode")
        log.info(
            f"Dispatching USER background task for URL: {request.url} with mode: {request.mode}"
        )
        task = scrape_for_user.delay(str(request.url), request.mode, request.output_format)
        response.status_code = 202  # Accepted
        return {"task_id": task.id, "status_endpoint": f"/tasks/{task.id}"}
    
    # For single_page: Execute synchronously
    if request.mode == "single_page":
        domain = urlparse(str(request.url)).netloc
        parser_config = CONFIGS.get(domain, GENERIC_CONFIG)
        log.info(
            f"Scraping URL: {request.url} using config for "
            f"'{domain if parser_config != GENERIC_CONFIG else 'generic'}'"
        )

        scraper = Scraper(parser_config=parser_config, cache=SHARED_CACHE)
        try:
            article = await scraper.scrape_url(str(request.url), output_format=request.output_format)
            if not article:
                raise HTTPException(
                    status_code=404,
                    detail="Could not extract a valid article from the URL.",
                )
            return article
        finally:
            await scraper.close()
    
    raise HTTPException(status_code=400, detail="Invalid scrape mode specified.")


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Checks the status of a background Celery task.
    
    Returns:
    - PENDING: Task is waiting to be executed
    - PROGRESS: Task is currently running
    - SUCCESS: Task completed successfully
    - FAILURE: Task failed with an error
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    if task_result.ready():
        result = task_result.result if task_result.successful() else None
    else:
        result = task_result.info

    # Sanitize heavy payloads from task result if any (e.g., remove 'articles')
    if isinstance(result, dict) and "articles" in result:
        result = {k: v for k, v in result.items() if k != "articles"}

    # Return only IDs here; full content is served via /scrapes endpoints
    ids = RESULTS_CACHE.get_task_ids(task_id)

    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": result,
        "article_ids": ids,
    }
@app.get("/scrapes/{task_id}")
async def get_scrape_result(
    task_id: str,
    include: Literal["ids", "compact", "full"] = "ids",
    offset: int = 0,
    limit: int = 50,
):
    """Fetch persisted scrape results by task id with pagination.

    Rules:
    - limit max = 50 (HTML payloads can be large; enforce small pages)
    - include=ids returns only paginated IDs
    - include=compact returns metadata slice WITHOUT content/raw_html
    - include=full currently acts like compact (content must be fetched via /article/{id})
    - Clients MUST call /article/{id} to retrieve article body
    """
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    ids = RESULTS_CACHE.get_task_ids(task_id)
    if ids is None:
        raise HTTPException(status_code=404, detail="Scrape result not found or expired")

    total = len(ids)
    end = min(offset + limit, total)
    page_ids = ids[offset:end]
    next_offset = end if end < total else None

    if include == "ids":
        return {
            "task_id": task_id,
            "total": total,
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset,
            "ids": page_ids,
        }

    # Build compact metadata slice, reconstruct if full list not stored
    articles_full = RESULTS_CACHE.get_task_full(task_id)
    compact_entries = []
    if articles_full:
        # We have a stored list; use direct slice matching IDs
        # Build mapping id->article for quick lookup
        mapping = {a.get("id"): a for a in articles_full if isinstance(a, dict)}
        for aid in page_ids:
            a = mapping.get(aid)
            if not a:
                continue
            compact_entries.append(
                {
                    "id": a.get("id"),
                    "title": a.get("title"),
                    "source_url": a.get("provenance", {}).get("source_url"),
                    "domain": a.get("provenance", {}).get("domain"),
                    "word_count": a.get("stats", {}).get("word_count"),
                    "format": a.get("content_format"),
                }
            )
    else:
        # Fall back: fetch each article from per-article cache
        for aid in page_ids:
            doc = RESULTS_CACHE.get_article(aid)
            if not doc:
                continue
            compact_entries.append(
                {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "source_url": doc.get("provenance", {}).get("source_url"),
                    "domain": doc.get("provenance", {}).get("domain"),
                    "word_count": doc.get("stats", {}).get("word_count"),
                    "format": doc.get("content_format"),
                }
            )

    # include==compact or include==full (full degraded to compact to force /article calls)
    return {
        "task_id": task_id,
        "total": total,
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset,
        "articles": compact_entries,
        "note": "Content omitted; fetch /article/{id} for body.",
    }

@app.get("/scrapes/{task_id}/urls")
async def get_scrape_urls(task_id: str, offset: int = 0, limit: int = 50):
    """Return a paginated slice of discovered URLs for a task (sitemap/rss).

    This uses the shared ScraperCache's per-task deque for large task introspection.
    """
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    total = SHARED_CACHE.get_task_queue_length(task_id)
    urls = SHARED_CACHE.get_task_urls_slice(task_id, start=offset, limit=limit)
    next_offset = offset + len(urls) if offset + len(urls) < total else None
    return {"task_id": task_id, "total": total, "offset": offset, "limit": limit, "next_offset": next_offset, "urls": urls}

@app.get("/scrapes/{task_id}/stats")
async def get_scrape_stats(task_id: str):
    """Return diagnostic stats for a scrape task (counts, failures list, etc)."""
    stats = RESULTS_CACHE.get_task_stats(task_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Stats not found or expired")
    # Flatten commonly used fields for convenience
    summary = stats.get("summary") if isinstance(stats, dict) else None
    total_urls = (summary or {}).get("total_urls")
    success_count = (summary or {}).get("success_count")
    fail_count = (summary or {}).get("fail_count")
    failed = (summary or {}).get("failed")
    failed_count = len(failed) if isinstance(failed, list) else None
    payload = {
        "task_id": task_id,
        "articles_found": stats.get("articles_found"),
        "total_chunks_processed": stats.get("total_chunks_processed"),
        "total_urls": total_urls,
        "success_count": success_count,
        "fail_count": fail_count,
        "failed_count": failed_count,
        "failed": failed,
    }
    return payload

@app.delete("/scrapes/{task_id}")
async def delete_scrape(task_id: str):
    """Delete cached results, stats and per-task URL queue for a task."""
    RESULTS_CACHE.delete_task(task_id)
    # Also clear URLs deque for task
    try:
        SHARED_CACHE.clear_task(task_id)
    except Exception:
        pass
    return {"task_id": task_id, "deleted": True}

@app.get("/article/{article_id}")
async def get_article_detail(article_id: str):
    """Fetch a single persisted article document."""
    from llm_scraper.cache import ArticlesCache  # ensure import path
    doc = RESULTS_CACHE.get_article(article_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Article not found or expired")
    return doc


@app.post("/query", response_model=QueryResponse)
async def query_rag_system(request: QueryRequest):
    """
    Performs a similarity search against the vector store.
    """
    try:
        engine = get_vector_store_engine()
        search_params = SearchRequest(query=request.query, limit=request.limit)
        results = engine.search(search_params)
        return {"query": request.query, "results": results}
    except ValueError as e:
        # This will catch configuration errors from lazy-loaded clients
        log.error(f"Configuration error during search: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Vector store is not configured correctly: {e}",
        )
    except Exception as e:
        log.error(f"Failed to perform query '{request.query}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An error occurred during the search: {e}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
