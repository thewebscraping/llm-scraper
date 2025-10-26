import asyncio
import json
import logging
from pathlib import Path

from llm_scraper import ParserConfig, Scraper, ScraperCache

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def scrape_with_config(parser_config: ParserConfig, cache: ScraperCache):
    """
    This function represents a single scraping task for one site.
    In a real-world scenario, this would be your Celery task.
    """
    log.info(f"--- Starting scrape for domain: {parser_config.domain} ---")
    scraper = Scraper(parser_config=parser_config, cache=cache)

    try:
        article_count = 0
        async for article in scraper.scrape_site(parser_config.domain):
            article_count += 1
            log.info(f"  [+] Scraped: {article.title} ({article.provenance.source_url})")

        if article_count == 0:
            log.warning(f"  [*] No new articles found for {parser_config.domain}.")
        else:
            log.info(f"  [+] Successfully scraped {article_count} new articles from {parser_config.domain}.")

    except Exception as e:
        log.error(f"  [!] An error occurred while scraping {parser_config.domain}: {e}", exc_info=True)
    finally:
        await scraper.close()
        log.info(f"--- Finished scrape for domain: {parser_config.domain} ---")


async def main():
    """
    Main function to discover JSON configs and run scraping tasks for each.
    This simulates a Celery Beat scheduler dispatching tasks.
    """
    # Use a single shared cache for all scrapers
    shared_cache = ScraperCache()
    log.info(f"Shared cache initialized. URLs in queue: {len(shared_cache)}")

    # Path to the directory containing your JSON configuration files
    config_dir = Path(__file__).parent / "src" / "llm_scraper" / "parsers" / "configs"
    log.info(f"Loading configurations from: {config_dir}")

    if not config_dir.exists():
        log.error(f"Configuration directory not found: {config_dir}")
        return

    # Discover and load all .json configuration files
    config_files = list(config_dir.glob("*.json"))
    if not config_files:
        log.warning("No JSON configuration files found in the directory.")
        return

    tasks = []
    for config_file in config_files:
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                parser_config = ParserConfig(**config_data)
                # Create an awaitable task for each configuration
                tasks.append(scrape_with_config(parser_config, shared_cache))
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            log.error(f"Failed to load or validate config file {config_file.name}: {e}")
        except Exception as e:
            log.error(f"An unexpected error occurred with {config_file.name}: {e}")

    # Run all scraping tasks concurrently
    if tasks:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
