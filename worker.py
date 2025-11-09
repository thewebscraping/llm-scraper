import asyncio
import json
import logging
from pathlib import Path
from typing import List

from celery import shared_task
from celery.schedules import crontab

from celery_app import celery_app
from llm_scraper import Article, ParserConfig, Scraper, ScraperCache
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
VECTOR_STORE_ENGINE = VectorStoreEngine(
    embedding_adapter=OpenAIEmbeddingAdapter(), db_adapter=AstraDBAdapter()
)


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


async def _scrape_and_collect_articles(scraper: Scraper, domain: str) -> List[Article]:
    """Helper async function to run the scraper and collect all articles."""
    articles = []
    async for article in scraper.scrape_site(domain):
        articles.append(article)
    return articles


# --- Celery Tasks ---
@shared_task(bind=True)
def scrape_site_for_rag(self, domain: str):
    """
    The main SYSTEM task to scrape a pre-configured site and update the RAG vector store.
    This task now processes articles in batches for efficiency.
    """
    log.info(f"[{self.request.id}] Starting SYSTEM scrape for domain: {domain}")
    self.update_state(state='PROGRESS', meta={'current_step': 'Loading configuration'})

    parser_config = load_parser_config(domain)
    if not parser_config:
        raise ValueError(f"Configuration for domain '{domain}' not found.")

    scraper = Scraper(parser_config=parser_config, cache=SHARED_CACHE)
    
    try:
        # Step 1: Scrape all articles first
        self.update_state(state='PROGRESS', meta={'current_step': 'Scraping all articles'})
        articles = asyncio.run(_scrape_and_collect_articles(scraper, domain))
        
        if not articles:
            self.update_state(state='SUCCESS', meta={'articles_found': 0, 'total_chunks_processed': 0})
            return f"Scrape for {domain} completed. No new articles found."

        self.update_state(state='PROGRESS', meta={'current_step': f'Processing {len(articles)} articles in batches'})
        
        total_chunks_processed = 0
        # Step 2: Process articles in batches
        for i in range(0, len(articles), BATCH_SIZE):
            batch = articles[i:i + BATCH_SIZE]
            documents_to_upsert: List[Document] = []
            
            log.info(f"[{self.request.id}] Processing batch {i//BATCH_SIZE + 1} with {len(batch)} articles.")

            for article in batch:
                chunks = article.chunk_by_token_estimate(max_tokens=512, overlap_tokens=50)
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
            upsert_request = UpsertRequest(documents=documents_to_upsert)
            VECTOR_STORE_ENGINE.upsert(params=upsert_request)
            total_chunks_processed += len(documents_to_upsert)
            
            self.update_state(state='PROGRESS', meta={
                'current_step': f'Processed batch {i//BATCH_SIZE + 1}',
                'total_chunks_processed': total_chunks_processed
            })

        self.update_state(state='SUCCESS', meta={'articles_found': len(articles), 'total_chunks_processed': total_chunks_processed})
        return f"Completed scrape for {domain}. Processed {len(articles)} articles and {total_chunks_processed} chunks."

    except Exception as e:
        log.error(f"[{self.request.id}] Task for {domain} failed: {e}", exc_info=True)
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        raise
    finally:
        asyncio.run(scraper.close())


# --- Celery Beat (Scheduler) Configuration ---
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    This function is called when Celery starts up. It sets up the recurring
    tasks for our system.
    """
    log.info("Setting up periodic tasks...")
    config_dir = Path.cwd() / "src" / "llm_scraper" / "parsers" / "configs"
    
    if not config_dir.is_dir():
        log.warning(f"Configs directory not found at {config_dir}. No periodic tasks scheduled.")
        return

    # For every configured site, create a scheduled task
    for config_file in config_dir.glob("*.json"):
        try:
            domain = json.load(open(config_file))["domain"]
            # Schedule the task to run every 4 hours
            sender.add_periodic_task(
                crontab(hour='*/4'),  # You can change the schedule here
                scrape_site_for_rag.s(domain),
                name=f'scrape-{domain}-every-4-hours'
            )
            log.info(f"Scheduled task for '{domain}' to run every 4 hours.")
        except (json.JSONDecodeError, KeyError):
            log.error(f"Could not schedule task for {config_file.name}, missing 'domain' field.")


