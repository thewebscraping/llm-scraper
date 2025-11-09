from __future__ import annotations

from typing import AsyncGenerator

import tls_requests

from .articles import Article
from .cache import ScraperCache
from .discovery import discover_urls
from .exceptions import ArticleCreationError
from .models.selector import ParserConfig


class Scraper:
    """
    A high-level scraper that orchestrates URL discovery, fetching,
    parsing, and caching.
    """

    def __init__(
        self,
        parser_config: ParserConfig,
        cache: ScraperCache,
        user_agent: str = "llm-scraper/1.0",
    ):
        """
        Initializes the Scraper.

        Args:
            parser_config: The parser configuration to use for extracting content.
            cache: A ScraperCache instance to manage seen URLs and the queue.
            user_agent: The User-Agent string to use for HTTP requests.
        """
        self.parser_config = parser_config
        self.cache = cache
        self.user_agent = user_agent
        self.http_client = tls_requests.AsyncClient(
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
            timeout=15.0,
        )

    async def scrape_site(self, domain: str) -> AsyncGenerator[Article, None]:
        """
        Discovers and scrapes all articles from a given domain.

        This method finds URLs from sitemaps and RSS feeds (respecting manual
        lists in the parser_config), then scrapes each new URL.

        Args:
            domain: The domain to scrape (e.g., "example.com").

        Yields:
            An Article object for each successfully scraped page.
        """
        # Discover URLs and add them to the cache queue
        initial_urls = await discover_urls(
            domain, self.parser_config, self.user_agent
        )
        new_urls_count = self.cache.add_urls(iter(initial_urls))
        print(f"Discovered {len(initial_urls)} URLs, {new_urls_count} were new.")

        # Process URLs from the queue
        while True:
            next_url = self.cache.get_next_url()
            if next_url is None:
                break  # No more URLs to process

            try:
                article = await self.scrape_url(next_url)
                if article:
                    yield article
            except Exception as e:
                print(f"Failed to scrape {next_url}: {e}")
                # Optionally, add to a failed queue for retrying later
                continue

    async def scrape_url(self, url: str, output_format: str = "markdown") -> Article | None:
        """
        Scrapes a single URL.

        Args:
            url: The URL to scrape.
            output_format: Content format - "markdown" (default) or "html"

        Returns:
            An Article object if successful, otherwise None.
        """
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            html = response.text
            
            # Use the Article.from_html factory to parse the content
            article = Article.from_html(
                html=html,
                url=str(response.url), # Convert URL object to string
                parser_config=self.parser_config,
                output_format=output_format
            )
            return article
        except tls_requests.HTTPError as e:
            print(f"HTTP error {e.response.status_code} for {url}")
        except ArticleCreationError as e:
            print(f"Could not create article from {url}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred for {url}: {e}")
        
        return None

    async def close(self):
        """Closes the underlying HTTP client."""
        await self.http_client.aclose()
