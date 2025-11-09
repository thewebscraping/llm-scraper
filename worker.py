import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Literal

from celery import Task, shared_task
from celery.schedules import crontab

from celery_app import celery_app
from llm_scraper import Article, GENERIC_CONFIG, ParserConfig, Scraper, ScraperCache
from llm_scraper.cache import ArticlesCache
from llm_scraper.vectors import (
    Document,
    UpsertRequest,
    VectorStoreEngine,
)
from llm_scraper.vectors.dbs.astradb import AstraDBAdapter
from llm_scraper.vectors.embeddings.openai import OpenAIEmbeddingAdapter

# --- Globals & Setup ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
import os

SHARED_CACHE = ScraperCache()
# Persist scraped results with TTL using diskcache
RESULTS_CACHE = ArticlesCache()
# Limit concurrent HTTP fetches/chrome to avoid overloading targets and our IO
MAX_CONCURRENT_SCRAPES = int(os.getenv("MAX_CONCURRENT_SCRAPES", "8"))
PER_SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "20"))
BATCH_SIZE = 20  # Process 20 articles at a time

# Initialize the vector store engine for the worker
_VECTOR_STORE_ENGINE: VectorStoreEngine | None = None


def get_vector_store_engine() -> VectorStoreEngine:
    """
    Initializes and returns a singleton instance of the VectorStoreEngine.
    This function will be called only when vector operations are needed,
    avoiding initialization on application startup.
    """
    global _VECTOR_STORE_ENGINE
    if _VECTOR_STORE_ENGINE is None:
        log.info("Initializing VectorStoreEngine for the first time.")
        _VECTOR_STORE_ENGINE = VectorStoreEngine(
            embedding_adapter=OpenAIEmbeddingAdapter(), db_adapter=AstraDBAdapter()
        )
    return _VECTOR_STORE_ENGINE


# --- Helper Function ---
def load_parser_config(domain: str) -> ParserConfig | None:
    """Load a parser config for a domain, searching recursively.

    Supports nested language folders (e.g. configs/en/c/crypto.news.json).
    Falls back to None (caller may use GENERIC_CONFIG) when not found.
    """
    config_dir = Path.cwd() / "src" / "llm_scraper" / "parsers" / "configs"
    if not config_dir.exists():
        log.warning(f"Config directory not found: {config_dir}")
        return None

    # Domain variants to try (strip common prefixes)
    domain_variants = {domain}
    if domain.startswith("www."):
        domain_variants.add(domain[4:])

    try:
        for variant in domain_variants:
            # Try filename match first
            for path in config_dir.rglob(f"{variant}.json"):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return ParserConfig(**data)
                except Exception as e:
                    log.error(f"Failed to parse config at {path}: {e}")
        # Fallback: inspect all json files and match on internal 'domain' field
        for path in config_dir.rglob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("domain") in domain_variants:
                    return ParserConfig(**data)
            except Exception:
                continue
    except Exception as e:
        log.error(f"Unexpected error searching configs for domain '{domain}': {e}")
        return None

    log.info(f"No specific parser config found for domain '{domain}'.")
    return None


async def _scrape_and_collect_articles(
    scraper: Scraper,
    url: str,
    mode: Literal["single_page", "sitemap", "rss"],
    output_format: Literal["markdown", "html"] = "markdown",
    task_id: str | None = None,
) -> tuple[List[Article], dict]:
    """Helper async function to run the scraper and collect all articles based on mode."""
    from llm_scraper.discovery import parse_sitemap, parse_rss_feed
    import tls_requests
    
    articles: List[Article] = []
    diagnostics = {
        "total_urls": 1 if mode == "single_page" else 0,
        "success_count": 0,
        "fail_count": 0,
        "failed": [],  # list of {url, error, status}
    }
    if mode == "single_page":
        try:
            article = await asyncio.wait_for(
                scraper.scrape_url(url, output_format=output_format),
                timeout=PER_SCRAPE_TIMEOUT,
            )
            if article:
                articles.append(article)
                diagnostics["success_count"] += 1
            else:
                diagnostics["fail_count"] += 1
                diagnostics["failed"].append({"url": url, "error": "empty article", "status": None})
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            log.warning(f"Single page scrape failed for {url}: {e} (status={status})")
            diagnostics["fail_count"] += 1
            diagnostics["failed"].append({"url": url, "error": str(e), "status": status})
        return articles, diagnostics
    elif mode == "sitemap":
        # Fetch sitemap and parse URLs
        async with tls_requests.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                urls = parse_sitemap(response.content)
            except Exception as e:
                log.error(f"Failed to fetch/parse sitemap {url}: {e}")
                return [], diagnostics
        
        # Deduplicate and cap concurrency
        urls = list(dict.fromkeys(urls))
        # Store discovered URLs under task queue for paging/inspection
        if task_id and urls:
            try:
                SHARED_CACHE.add_task_urls(task_id, urls)
            except Exception as e:
                log.warning(f"Failed to enqueue task URLs for {task_id}: {e}")
        diagnostics["total_urls"] = len(urls)
        sem = asyncio.Semaphore(max(1, min(MAX_CONCURRENT_SCRAPES, len(urls))))

        async def scrape_one(u: str):
            async with sem:
                try:
                    art = await asyncio.wait_for(
                        scraper.scrape_url(u, output_format=output_format),
                        timeout=PER_SCRAPE_TIMEOUT,
                    )
                    return art, None
                except Exception as e:
                    status = getattr(getattr(e, "response", None), "status_code", None)
                    log.warning(f"Scrape failed for {u}: {e} (status={status})")
                    return None, {"url": u, "error": str(e), "status": status}

        results = await asyncio.gather(*(scrape_one(u) for u in urls), return_exceptions=False)
        for art, err in results:
            if art:
                articles.append(art)
                diagnostics["success_count"] += 1
            elif err:
                diagnostics["fail_count"] += 1
                diagnostics["failed"].append(err)
    elif mode == "rss":
        # Fetch RSS feed and parse URLs
        async with tls_requests.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                urls = parse_rss_feed(response.content)
            except Exception as e:
                log.error(f"Failed to fetch/parse RSS {url}: {e}")
                return [], diagnostics
        
        # Scrape each URL
        urls = list(dict.fromkeys(urls))
        if task_id and urls:
            try:
                SHARED_CACHE.add_task_urls(task_id, urls)
            except Exception as e:
                log.warning(f"Failed to enqueue task URLs for {task_id}: {e}")
        diagnostics["total_urls"] = len(urls)
        sem = asyncio.Semaphore(max(1, min(MAX_CONCURRENT_SCRAPES, len(urls))))

        async def scrape_one(u: str):
            async with sem:
                try:
                    art = await asyncio.wait_for(
                        scraper.scrape_url(u, output_format=output_format),
                        timeout=PER_SCRAPE_TIMEOUT,
                    )
                    return art, None
                except Exception as e:
                    status = getattr(getattr(e, "response", None), "status_code", None)
                    log.warning(f"Scrape failed for {u}: {e} (status={status})")
                    return None, {"url": u, "error": str(e), "status": status}

        results = await asyncio.gather(*(scrape_one(u) for u in urls), return_exceptions=False)
        for art, err in results:
            if art:
                articles.append(art)
                diagnostics["success_count"] += 1
            elif err:
                diagnostics["fail_count"] += 1
                diagnostics["failed"].append(err)
    return articles, diagnostics


# --- Celery Tasks ---
@shared_task(bind=True)
def scrape_for_user(
    self: Task, url: str, mode: Literal["single_page", "sitemap", "rss"], output_format: Literal["markdown", "html"] = "markdown"
):
    """
    USER task to scrape URLs and return articles.
    Does NOT store in vector database - just returns scraped content.
    """
    log.info(f"[{self.request.id}] Starting USER scrape for URL: {url} with mode: {mode}")
    self.update_state(state="PROGRESS", meta={"current_step": "Loading configuration"})

    domain = urlparse(url).netloc
    parser_config = load_parser_config(domain)
    if not parser_config:
        log.warning(f"No specific config for '{domain}', using generic config.")
        parser_config = GENERIC_CONFIG

    scraper = Scraper(parser_config=parser_config, cache=SHARED_CACHE)

    try:
        self.update_state(
            state="PROGRESS", meta={"current_step": f"Scraping URL(s) via {mode}"}
        )
        articles, diag = asyncio.run(
            _scrape_and_collect_articles(
                scraper,
                url,
                mode,
                output_format,
                task_id=self.request.id,
            )
        )

        if not articles:
            self.update_state(
                state="PROGRESS",
                meta={"articles_found": 0, "message": "No articles found", "summary": diag},
            )
            return {"articles": [], "count": 0}

        # Convert articles to dict for JSON serialization
        articles_data = []
        for article in articles:
            # Build a safe serializable dict; Article doesn't expose content_markdown/content_html
            # Use cleaned text in 'content'. Raw HTML (if captured) under 'raw_html'.
            item = {
                "id": article.id,
                "title": article.title,
                "content": article.content,
                "raw_html": article.raw_html,  # may be None
                "content_format": output_format,
                "provenance": {
                    "source_url": str(article.provenance.source_url),
                    "domain": article.provenance.domain,
                },
                "metadata": article.metadata.model_dump() if article.metadata else {},
                "stats": {
                    "word_count": article.computed_word_count,
                    "reading_time_minutes": article.computed_reading_time,
                },
            }
            articles_data.append(item)

        # Persist results with TTL if configured
        ttl_days_env = os.getenv("SCRAPE_RESULT_TTL_DAYS", "7")
        try:
            ttl_days = float(ttl_days_env)
        except Exception:
            ttl_days = 7.0
        # Respect max store full threshold to avoid huge payloads
        max_full_env = os.getenv("SCRAPE_RESULT_MAX_FULL", "1000")
        try:
            max_full = int(max_full_env)
        except Exception:
            max_full = 1000
        RESULTS_CACHE.save_task_result(
            self.request.id,
            articles_data,
            ttl_days=ttl_days,
            max_store_full=max_full,
        )
        # Save diagnostic stats alongside results for API consumption
        RESULTS_CACHE.save_task_stats(
            self.request.id,
            {"summary": diag, "articles_found": len(articles_data)},
            ttl_days=ttl_days,
        )

        self.update_state(
            state="PROGRESS",
            meta={"articles_found": len(articles_data), "summary": diag},
        )
        return {
            "article_ids": [a["id"] for a in articles_data],
            "count": len(articles_data),
            "message": f"Successfully scraped {len(articles_data)} articles",
            "summary": diag,
        }

    except Exception as e:
        log.error(f"[{self.request.id}] USER task for {url} failed: {e}", exc_info=True)
        self.update_state(
            state="FAILURE", meta={"exc_type": type(e).__name__, "exc_message": str(e)}
        )
        raise
    finally:
        asyncio.run(scraper.close())


@shared_task(bind=True)
def scrape_site_for_rag(
    self: Task, url: str, mode: Literal["single_page", "sitemap", "rss"], output_format: Literal["markdown", "html"] = "markdown"
):
    """
    The main SYSTEM task to scrape a URL based on the specified mode and update the RAG vector store.
    """
    log.info(f"[{self.request.id}] Starting SYSTEM scrape for URL: {url} with mode: {mode}")
    self.update_state(state="PROGRESS", meta={"current_step": "Loading configuration"})

    domain = urlparse(url).netloc
    parser_config = load_parser_config(domain)
    if not parser_config:
        # For single page scrapes, we can allow a generic fallback
        if mode == "single_page":
            log.warning(f"No specific config for '{domain}', using generic config.")
            parser_config = GENERIC_CONFIG
        else:
            raise ValueError(f"Configuration for domain '{domain}' not found.")

    scraper = Scraper(parser_config=parser_config, cache=SHARED_CACHE)

    try:
        # Step 1: Scrape all articles based on the mode
        self.update_state(
            state="PROGRESS", meta={"current_step": f"Scraping URL(s) via {mode}"}
        )
        articles, diag = asyncio.run(
            _scrape_and_collect_articles(
                scraper,
                url,
                mode,
                output_format,
                task_id=self.request.id,
            )
        )

        if not articles:
            self.update_state(
                state="PROGRESS",
                meta={"articles_found": 0, "total_chunks_processed": 0, "summary": diag},
            )
            return f"Scrape for {url} completed. No new articles found."

        self.update_state(
            state="PROGRESS",
            meta={"current_step": f"Processing {len(articles)} articles in batches"},
        )

        total_chunks_processed = 0
        # Step 2: Process articles in batches
        for i in range(0, len(articles), BATCH_SIZE):
            batch = articles[i : i + BATCH_SIZE]
            documents_to_upsert: List[Document] = []

            log.info(
                f"[{self.request.id}] Processing batch {i//BATCH_SIZE + 1} with {len(batch)} articles."
            )

            for article in batch:
                # The cache is now primarily for preventing re-scraping entire sites,
                # but we can still check individual article URLs if needed.
                # Here, we assume the scraper's internal logic handles duplicates
                # from sitemaps/RSS feeds within a single run.
                chunks = article.chunk_by_token_estimate(
                    max_tokens=512, overlap_tokens=50
                )
                if not chunks:
                    continue

                for chunk in chunks:
                    doc = Document(
                        id=f"{article.id}-chunk-{chunk.index}",
                        text=chunk.content,
                        metadata={
                            "title": article.title,
                            "source_url": str(article.provenance.source_url),
                            "domain": article.provenance.domain,
                        },
                    )
                    documents_to_upsert.append(doc)

            if not documents_to_upsert:
                continue

            # Step 3: Upsert each batch to the vector store using the engine
            try:
                engine = get_vector_store_engine()
                upsert_request = UpsertRequest(documents=documents_to_upsert)
                engine.upsert(upsert_request)
                total_chunks_processed += len(documents_to_upsert)
            except ValueError as e:
                log.error(
                    f"Skipping vector store upsert due to configuration error: {e}"
                )
                # Continue processing other batches even if one fails due to config
                pass

            self.update_state(
                state="PROGRESS",
                meta={
                    "current_step": f"Processed batch {i//BATCH_SIZE + 1}",
                    "total_chunks_processed": total_chunks_processed,
                },
            )

        self.update_state(
            state="PROGRESS",
            meta={
                "articles_found": len(articles),
                "total_chunks_processed": total_chunks_processed,
                "summary": diag,
            },
        )
        # Save stats for system task as well
        RESULTS_CACHE.save_task_stats(
            self.request.id,
            {
                "summary": diag,
                "articles_found": len(articles),
                "total_chunks_processed": total_chunks_processed,
            },
            ttl_days=float(os.getenv("SCRAPE_RESULT_TTL_DAYS", "7")),
        )
        return f"Completed scrape for {url}. Processed {len(articles)} articles and {total_chunks_processed} chunks."

    except Exception as e:
        log.error(f"[{self.request.id}] Task for {url} failed: {e}", exc_info=True)
        self.update_state(
            state="FAILURE", meta={"exc_type": type(e).__name__, "exc_message": str(e)}
        )
        raise
    finally:
        asyncio.run(scraper.close())


# --- Celery Beat (Scheduler) Configuration ---
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    This function is called when Celery starts up. It sets up the recurring
    tasks for our system. It now schedules tasks based on sitemap and RSS
    feeds defined in the parser configs.
    """
    log.info("Setting up periodic tasks...")
    config_dir = Path.cwd() / "src" / "llm_scraper" / "parsers" / "configs"

    if not config_dir.is_dir():
        log.warning(
            f"Configs directory not found at {config_dir}. No periodic tasks scheduled."
        )
        return

    # For every configured site, create scheduled tasks for sitemaps and RSS feeds
    for config_file in config_dir.rglob("*.json"):
        try:
            config_data = json.load(open(config_file))
            domain = config_data.get("domain")
            if not domain:
                log.error(
                    f"Could not schedule task for {config_file.name}, missing 'domain' field."
                )
                continue

            # Schedule sitemap scraping (e.g., every 6 hours)
            if config_data.get("sitemap_url"):
                sender.add_periodic_task(
                    crontab(hour="*/6"),
                    scrape_site_for_rag.s(
                        url=config_data["sitemap_url"], mode="sitemap"
                    ),
                    name=f"scrape-sitemap-{domain}",
                )
                log.info(f"Scheduled sitemap task for '{domain}' to run every 6 hours.")

            # Schedule RSS feed scraping (e.g., every 15 minutes for fresh content)
            if config_data.get("rss_url"):
                sender.add_periodic_task(
                    crontab(minute="*/15"),
                    scrape_site_for_rag.s(url=config_data["rss_url"], mode="rss"),
                    name=f"scrape-rss-{domain}",
                )
                log.info(f"Scheduled RSS task for '{domain}' to run every 15 minutes.")

        except (json.JSONDecodeError, KeyError) as e:
            log.error(
                f"Could not schedule task for {config_file.name} due to error: {e}"
            )


