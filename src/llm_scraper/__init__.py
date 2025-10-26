"""
LLM Scraper
"""
__version__ = "0.0.1"

from .articles import Article, ArticleChunk
from .cache import ScraperCache
from .chunking import chunk_text_by_char, chunk_text_by_token_estimate
from .exceptions import ArticleCreationError
from .models.selector import ElementSelector, ParserConfig
from .presets import GENERIC_CONFIG, WORDPRESS_CONFIG
from .scraper import Scraper

__all__ = [
    "Article",
    "ArticleChunk",
    "ArticleCreationError",
    "ElementSelector",
    "ParserConfig",
    "Scraper",
    "ScraperCache",
    "GENERIC_CONFIG",
    "WORDPRESS_CONFIG",
    "chunk_text_by_char",
    "chunk_text_by_token_estimate",
]
