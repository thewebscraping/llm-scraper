import asyncio
import logging

from llm_scraper import GENERIC_CONFIG, Scraper, ScraperCache

# Configure logging to see the output from the scraper
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def main():
    """
    An example function demonstrating how to use the Scraper to automate
    the discovery and scraping of articles from a website.
    """
    # 1. Initialize the cache.
    # This will create a cache in your home directory (`~/.llm_scraper_cache`)
    # to keep track of URLs to visit and which ones have already been seen.
    # The cache is persistent across runs.
    cache = ScraperCache()
    log.info(f"Cache initialized. URLs in queue: {len(cache)}")

    # 2. Initialize the Scraper.
    # We provide it with a parser configuration (here, the generic one)
    # and the cache instance.
    scraper = Scraper(parser_config=GENERIC_CONFIG, cache=cache)
    log.info("Scraper initialized with GENERIC_CONFIG.")

    # 3. Define the target domain and start scraping.
    # The `scrape_site` method will first discover URLs from the domain's
    # sitemaps and RSS feeds, add new ones to the cache, and then process
    # them one by one.
    domain_to_scrape = "theverge.com"
    log.info(f"Starting scrape for domain: {domain_to_scrape}")

    try:
        # We iterate through the asynchronous generator provided by `scrape_site`.
        # It will yield an `Article` object for each successfully scraped page.
        article_count = 0
        async for article in scraper.scrape_site(domain_to_scrape):
            article_count += 1
            log.info("--- Successfully scraped an article ---")
            print(f"  Title: {article.title}")
            print(f"  URL: {article.provenance.source_url}")
            print(f"  Word Count: {article.computed_word_count}")
            # You can also chunk the article content easily
            # article.chunk_by_token_estimate(max_tokens=512)
            # print(f"  Chunks created: {len(article.chunks)}")
            print("-" * 40)

        if article_count == 0:
            log.warning(
                "No new articles were scraped. This might be because they are "
                "already in the cache from a previous run."
            )

    except Exception as e:
        log.error(f"An error occurred during the scraping process: {e}", exc_info=True)
    finally:
        # 4. It's important to close the scraper's underlying HTTP client
        # to release resources gracefully.
        await scraper.close()
        log.info("Scraping process finished and resources released.")


if __name__ == "__main__":
    # For Windows, you might need to set a different event loop policy
    # if you encounter issues with asyncio.
    # if sys.platform == "win32":
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
