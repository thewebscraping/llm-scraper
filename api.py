import logging
from pathlib import Path
import json
from typing import Dict, List, Literal, Union
from urllib.parse import urlparse

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, HttpUrl

from celery_app import celery_app
from llm_scraper import GENERIC_CONFIG, Article, ParserConfig, Scraper, ScraperCache
from llm_scraper.vectors import (
    Document,
    SearchRequest,
    UpsertRequest,
    VectorStoreEngine,
)
from llm_scraper.vectors.dbs.astradb import AstraDBAdapter
from llm_scraper.vectors.embeddings.openai import OpenAIEmbeddingAdapter
from worker import scrape_site_for_rag

# --- Globals ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scraper_api")
SHARED_CACHE = ScraperCache()
CONFIGS: Dict[str, ParserConfig] = {}

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


class TaskResponse(BaseModel):
    task_id: str
    status_endpoint: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: str | dict | None


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


class QueryResponse(BaseModel):
    query: str
    results: List[dict]


# --- API Endpoints ---
@app.post("/scrape", response_model=Union[Article, TaskResponse])
async def scrape(request: ScrapeRequest, response: Response):
    """
    Triggers a scraping process based on the specified mode.

    - **single_page**: Scrapes a single article URL and returns the content directly.
    - **sitemap**: Triggers a background task to scrape all URLs in a sitemap.
    - **rss**: Triggers a background task to scrape all URLs from an RSS feed.
    """
    # --- Asynchronous Task for Sitemap/RSS ---
    if request.mode in ["sitemap", "rss"]:
        log.info(
            f"Dispatching background task for URL: {request.url} with mode: {request.mode}"
        )
        task = scrape_site_for_rag.delay(str(request.url), request.mode)
        response.status_code = 202  # Accepted
        return {"task_id": task.id, "status_endpoint": f"/tasks/{task.id}"}

    # --- Synchronous Execution for a Single Page ---
    if request.mode == "single_page":
        domain = urlparse(str(request.url)).netloc
        parser_config = CONFIGS.get(domain, GENERIC_CONFIG)
        log.info(
            f"Scraping URL: {request.url} using config for "
            f"'{domain if parser_config != GENERIC_CONFIG else 'generic'}'"
        )

        scraper = Scraper(parser_config=parser_config, cache=SHARED_CACHE)
        try:
            article = await scraper.scrape_url(str(request.url))
            if not article:
                raise HTTPException(
                    status_code=404,
                    detail="Could not extract a valid article from the URL.",
                )
            return article
        finally:
            await scraper.close()

    # This part should not be reachable if mode is validated by Pydantic
    raise HTTPException(status_code=400, detail="Invalid scrape mode specified.")


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Checks the status of a background Celery task."""
    task_result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else task_result.info,
    }
    return response


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
