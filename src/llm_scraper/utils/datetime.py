"""
Datetime utilities for the LLM scraper.

This module provides datetime-related helper functions.
"""
from __future__ import annotations

from datetime import datetime, timezone

__all__ = [
    "now_utc",
]


def now_utc() -> datetime:
    """
    Get current UTC datetime with timezone awareness.

    Returns:
        A timezone-aware datetime object representing the current UTC time.

    Examples:
        >>> from datetime import timezone
        >>> dt = now_utc()
        >>> dt.tzinfo == timezone.utc
        True
    """
    return datetime.now(timezone.utc)
