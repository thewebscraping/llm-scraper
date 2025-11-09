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
SHARED_CACHE = ScraperCache()
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
    """Loads a specific parser configuration from the configs directory."""
    # Assume the worker is run from the project root
    config_dir = Path.cwd() / "src" / "llm_scraper" / "parsers" / "configs"
    config_file = config_dir / f"{domain}.json"
    if not config_file.exists():
        log.error(f"Config file for domain '{domain}' not found at {config_file}")
        return None
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        return ParserConfig(**config_data)
    except Exception as e:
        log.error(f"Failed to load or validate config for {domain}: {e}")
        return None


async def _scrape_and_collect_articles(
    scraper: Scraper, url: str, mode: Literal["single_page", "sitemap", "rss"]
) -> List[Article]:
    """Helper async function to run the scraper and collect all articles based on mode."""
    articles = []
    if mode == "single_page":
        article = await scraper.scrape_url(url)
        if article:
            articles.append(article)
    elif mode == "sitemap":
        async for article in scraper.scrape_sitemap(url):
            articles.append(article)
    elif mode == "rss":
        async for article in scraper.scrape_rss_feed(url):
            articles.append(article)
    return articles


# --- Celery Tasks ---
@shared_task(bind=True)
def scrape_site_for_rag(
    self: Task, url: str, mode: Literal["single_page", "sitemap", "rss"]
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
        articles = asyncio.run(_scrape_and_collect_articles(scraper, url, mode))

        if not articles:
            self.update_state(
                state="SUCCESS",
                meta={"articles_found": 0, "total_chunks_processed": 0},
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
            state="SUCCESS",
            meta={
                "articles_found": len(articles),
                "total_chunks_processed": total_chunks_processed,
            },
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
    for config_file in config_dir.glob("*.json"):
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


