from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from typing import Deque as DequeType
from typing import Iterator

from diskcache import Deque, Index, Cache


def _get_default_cache_dir() -> Path:
    """Returns the default cache directory."""
    return Path.home() / ".llm_scraper_cache"


def _compute_cache_key(value: str, *, algorithm: str = "md5", secret: str | None = None) -> str:
    """Compute a stable cache key for a value.

    Parameters:
        value: Input string to hash.
        algorithm: One of 'md5', 'sha1', 'sha256', 'hmac-sha256'. Defaults to md5 for backward compatibility.
        secret: Optional secret salt; if provided and algorithm starts with 'hmac', HMAC will be used.

    Returns:
        Hex digest string.

    Notes:
        - Existing data hashed with plain MD5 remains valid because default stays md5.
        - Future migration: set env LLM_SCRAPER_HASH_ALGO + LLM_SCRAPER_HASH_SECRET to upgrade without code changes.
    """
    algo = (algorithm or "md5").lower()
    if algo == "md5":
        return hashlib.md5(value.encode("utf-8")).hexdigest()
    if algo == "sha1":
        return hashlib.sha1(value.encode("utf-8")).hexdigest()
    if algo == "sha256":
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    if algo in {"hmac-sha256", "hmac_sha256"}:
        if not secret:
            raise ValueError("Secret required for hmac-sha256")
        return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()
    # Fallback to md5 if unknown to avoid runtime breakage
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
        # Per-task URL queues (for large sitemap/rss tasks). We lazy-create deques.
        self._task_queues_dir = self.cache_dir / "tasks"
        self._task_queues_dir.mkdir(parents=True, exist_ok=True)
        self._task_queues: dict[str, DequeType[str]] = {}

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
        # Backward compatible key derivation
        from os import getenv
        algo = getenv("LLM_SCRAPER_HASH_ALGO", "md5")
        secret = getenv("LLM_SCRAPER_HASH_SECRET")
        return _compute_cache_key(url, algorithm=algo, secret=secret) in self._seen_urls

    def mark_as_seen(self, url: str) -> None:
        """
        Marks a URL as 'seen' to prevent it from being processed again.

        Args:
            url: The URL to mark as seen.
        """
        from os import getenv
        algo = getenv("LLM_SCRAPER_HASH_ALGO", "md5")
        secret = getenv("LLM_SCRAPER_HASH_SECRET")
        self._seen_urls[_compute_cache_key(url, algorithm=algo, secret=secret)] = True

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
        # Clear all task-specific queues
        for q in self._task_queues.values():
            q.clear()

    # --- Task-specific URL queue management ---
    def _get_task_queue(self, task_id: str) -> DequeType[str]:
        """Return (and create if needed) the deque for a specific task id."""
        if task_id not in self._task_queues:
            q_dir = self._task_queues_dir / task_id
            q_dir.mkdir(parents=True, exist_ok=True)
            self._task_queues[task_id] = Deque(directory=str(q_dir))
        return self._task_queues[task_id]

    def add_task_urls(self, task_id: str, urls: list[str]) -> int:
        """Append discovered sitemap/RSS URLs for a task without marking them as seen.

        These queues are for introspection & pagination of extremely large tasks.
        """
        if not urls:
            return 0
        q = self._get_task_queue(task_id)
        for u in urls:
            q.append(u)
        return len(urls)

    def get_task_queue_length(self, task_id: str) -> int:
        q = self._get_task_queue(task_id)
        return len(q)

    def get_task_urls_slice(self, task_id: str, start: int = 0, limit: int = 100) -> list[str]:
        """Return a slice of the stored URLs for a task (without loading all into memory)."""
        if limit <= 0:
            return []
        q = self._get_task_queue(task_id)
        end = start + limit
        out: list[str] = []
        # Iterate efficiently; Deque does not support slicing directly
        for i, url in enumerate(q):
            if i >= end:
                break
            if i >= start:
                out.append(url)
        return out

    def clear_task(self, task_id: str) -> None:
        """Remove all stored URLs for a given task."""
        if task_id in self._task_queues:
            self._task_queues[task_id].clear()
            del self._task_queues[task_id]


class ArticlesCache:
    """
    A lightweight article/result store backed by diskcache with optional TTL.

    This stores:
    - Per-task compact list of article IDs (task:<task_id>:ids)
    - Per-task full result payload (task:<task_id>:full)
    - Per-article detailed document (article:<article_id>)

    Use cases:
    - Return small payloads (IDs) in APIs, fetch details on-demand
    - Auto-expire scraped content after N days to save space
    """

    def __init__(self, cache_dir: Path | str | None = None):
        base = _get_default_cache_dir() if cache_dir is None else Path(cache_dir)
        self._dir = base / "articles"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache = Cache(directory=str(self._dir))

    @staticmethod
    def _days_to_seconds(days: int | float | None) -> int | None:
        if days is None:
            return None
        try:
            return int(float(days) * 24 * 3600)
        except Exception:
            return None

    def save_task_result(
        self,
        task_id: str,
        articles: list[dict],
        ttl_days: int | float | None = None,
        max_store_full: int | None = None,
    ) -> None:
        """Persist a task's scraped result.

        - Saves compact IDs list under task key
        - Saves full payload under task key
        - Saves each article under article key
        """
        expire = self._days_to_seconds(ttl_days)

        ids = [a.get("id") for a in articles if isinstance(a, dict) and a.get("id")]
        # Per-task compact and (optionally) full
        self._cache.set(f"task:{task_id}:ids", ids, expire=expire)
        if max_store_full is None or len(articles) <= max_store_full:
            self._cache.set(f"task:{task_id}:full", articles, expire=expire)

        # Per-article details (optional but useful)
        for a in articles:
            aid = a.get("id") if isinstance(a, dict) else None
            if aid:
                self._cache.set(f"article:{aid}", a, expire=expire)

    def save_task_stats(self, task_id: str, stats: dict, ttl_days: int | float | None = None) -> None:
        expire = self._days_to_seconds(ttl_days)
        self._cache.set(f"task:{task_id}:stats", stats, expire=expire)

    def get_task_stats(self, task_id: str) -> dict | None:
        return self._cache.get(f"task:{task_id}:stats")

    def get_task_ids(self, task_id: str) -> list[str] | None:
        return self._cache.get(f"task:{task_id}:ids")

    def get_task_full(self, task_id: str) -> list[dict] | None:
        return self._cache.get(f"task:{task_id}:full")

    def get_article(self, article_id: str) -> dict | None:
        return self._cache.get(f"article:{article_id}")

    def delete_task(self, task_id: str) -> None:
        self._cache.delete(f"task:{task_id}:ids")
        self._cache.delete(f"task:{task_id}:full")
        self._cache.delete(f"task:{task_id}:stats")

    def delete_article(self, article_id: str) -> None:
        self._cache.delete(f"article:{article_id}")
