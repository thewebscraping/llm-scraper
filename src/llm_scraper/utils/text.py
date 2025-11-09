"""
Text processing utilities for the LLM scraper.

This module provides utilities for text analysis, token estimation, 
word counting, and hashing functions.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Pattern

__all__ = [
    "WORD_RE",
    "estimate_tokens_from_text",
    "count_words",
    "sha256_hex",
]

# Unicode-aware word matching regex
WORD_RE: Pattern[str] = re.compile(r"\w+", re.UNICODE)


def estimate_tokens_from_text(text: str, avg_token_per_word: float = 1.33) -> int:
    """
    Provides a fast, heuristic-based estimate of token count for a given text.

    This method is a safe and quick way to approximate tokenization without needing
    to load a full tokenizer. It's based on the average number of tokens per word,
    which is a reasonable approximation for many subword tokenization strategies.

    Args:
        text: The input string to estimate tokens for.
        avg_token_per_word: The average token-to-word ratio. The default of 1.33
                            is a good starting point for many models (GPT-3/4, etc.).

    Returns:
        An integer representing the estimated number of tokens.

    Examples:
        >>> estimate_tokens_from_text("Hello world")
        3
        >>> estimate_tokens_from_text("The quick brown fox jumps over the lazy dog")
        12
        >>> estimate_tokens_from_text("")
        0
    """
    if not text:
        return 0
    words = len(WORD_RE.findall(text))
    return int(math.ceil(words * avg_token_per_word))


def count_words(text: str) -> int:
    """
    Count words in text using unicode-aware regex.

    Args:
        text: The input string to count words in.

    Returns:
        The number of words found in the text.

    Examples:
        >>> count_words("Hello world")
        2
        >>> count_words("こんにちは世界")  # Japanese
        2
        >>> count_words("")
        0
    """
    if not text:
        return 0
    return len(WORD_RE.findall(text))


def sha256_hex(value: str) -> str:
    """
    Generate a SHA-256 hexadecimal hash from a string.

    Args:
        value: The string to hash.

    Returns:
        The hexadecimal representation of the SHA-256 hash.

    Examples:
        >>> sha256_hex("hello")
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
        >>> len(sha256_hex("test"))
        64
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
