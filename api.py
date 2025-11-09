import logging
from pathlib import Path
import json
from typing import Dict, List
from urllib.parse import urlparse

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
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

# Initialize the vector store engine with concrete adapters
VECTOR_STORE_ENGINE = VectorStoreEngine(
    embedding_adapter=OpenAIEmbeddingAdapter(), db_adapter=AstraDBAdapter()
)


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
class ScrapeUrlRequest(BaseModel):
    url: HttpUrl
    output_format: str = "markdown"  # "markdown" or "html"


class ScrapeSiteRequest(BaseModel):
    domain: str


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
@app.post("/scrape-url", response_model=Article)
async def scrape_single_url(request: ScrapeUrlRequest):
    """
    Scrapes a single URL on-demand without storing it in the main RAG store.
    This is for quick, one-off extractions by users.
    
    Args:
        url: The URL to scrape
        output_format: Content format - "markdown" (default) or "html"
    """
    # Validate output format
    if request.output_format not in ("markdown", "html"):
        raise HTTPException(
            status_code=400, 
            detail="output_format must be 'markdown' or 'html'"
        )
    
    domain = urlparse(str(request.url)).netloc
    parser_config = CONFIGS.get(domain, GENERIC_CONFIG)
    log.info(
        f"Scraping URL: {request.url} using config for "
        f"'{domain if parser_config != GENERIC_CONFIG else 'generic'}' "
        f"with output_format='{request.output_format}'"
    )

    scraper = Scraper(parser_config=parser_config, cache=SHARED_CACHE)
    try:
        article = await scraper.scrape_url(
            str(request.url),
            output_format=request.output_format
        )
        if not article:
            raise HTTPException(
                status_code=404, 
                detail="Could not extract a valid article from the URL."
            )
        return article
    finally:
        await scraper.close()


@app.post("/scrape-site", response_model=TaskResponse)
async def trigger_site_scrape(request: ScrapeSiteRequest):
    """
    Triggers a background Celery task to scrape an entire site and update
    the main RAG vector store. This is for USER-initiated system tasks.
    """
    domain = request.domain
    if domain not in CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"No configuration found for domain '{domain}'.",
        )

    log.info(f"Dispatching background task to scrape site: {domain}")
    task = scrape_site_for_rag.delay(domain)

    return {
        "task_id": task.id,
        "status_endpoint": f"/tasks/{task.id}",
    }


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
        search_params = SearchRequest(query=request.query, limit=request.limit)
        results = VECTOR_STORE_ENGINE.search(params=search_params)
        return {"query": request.query, "results": results}
    except Exception as e:
        log.error(f"Failed to perform query '{request.query}': {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An error occurred during the search: {e}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
