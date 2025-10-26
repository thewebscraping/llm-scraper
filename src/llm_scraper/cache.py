from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Deque as DequeType
from typing import Iterator

from diskcache import Deque, Index


def _get_default_cache_dir() -> Path:
    """Returns the default cache directory."""
    return Path.home() / ".llm_scraper_cache"


def _md5_hash(value: str) -> str:
    """Generates an MD5 hash for a given string."""
    return hashlib.md5(value.encode("utf-8")).hexdigest()


class ScraperCache:
    """
    A persistent cache for the scraper, built on top of `diskcache`.

    This class manages a queue of URLs to be processed and a set of 'seen' URLs
    to prevent re-processing. It is designed to be persistent across runs.
    """

    def __init__(self, cache_dir: Path | str | None = None):
        """
        Initializes the cache.

        Args:
            cache_dir: The directory to store the cache files. If None, a default
                       directory in the user's home folder is used.
        """
        if cache_dir is None:
            self.cache_dir = _get_default_cache_dir()
        else:
            self.cache_dir = Path(cache_dir)

        # Ensure the cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._url_queue: DequeType[str] = Deque(directory=str(self.cache_dir / "url_queue"))
        self._seen_urls: Index = Index(str(self.cache_dir / "seen_urls"))

    def add_url(self, url: str) -> bool:
        """
        Adds a URL to the processing queue if it has not been seen before.

        Args:
            url: The URL to add.

        Returns:
            True if the URL was added, False if it was already in the cache.
        """
        if self.has_url(url):
            return False
        self._url_queue.append(url)
        self.mark_as_seen(url)
        return True

    def add_urls(self, urls: Iterator[str]) -> int:
        """
        Adds multiple URLs to the queue.

        Args:
            urls: An iterator of URLs to add.

        Returns:
            The number of new URLs that were added to the queue.
        """
        added_count = 0
        for url in urls:
            if self.add_url(url):
                added_count += 1
        return added_count

    def has_url(self, url: str) -> bool:
        """
        Checks if a URL has been seen before.

        Args:
            url: The URL to check.

        Returns:
            True if the URL has been seen, False otherwise.
        """
        return _md5_hash(url) in self._seen_urls

    def mark_as_seen(self, url: str) -> None:
        """
        Marks a URL as 'seen' to prevent it from being processed again.

        Args:
            url: The URL to mark as seen.
        """
        self._seen_urls[_md5_hash(url)] = True

    def get_next_url(self) -> str | None:
        """
        Retrieves the next URL from the queue.

        Returns:
            The next URL, or None if the queue is empty.
        """
        try:
            return self._url_queue.popleft()
        except IndexError:
            return None

    def __len__(self) -> int:
        """Returns the number of URLs currently in the queue."""
        return len(self._url_queue)

    def clear(self) -> None:
        """Clears the entire cache, including the URL queue and the seen set."""
        self._url_queue.clear()
        self._seen_urls.clear()
