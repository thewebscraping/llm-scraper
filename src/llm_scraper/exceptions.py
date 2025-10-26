__all__ = (
    "ScraperError",
    "ParserError",
    "URLParserError",
)


class ScraperError(Exception):
    """Base Scraper Error"""


class ParserError(Exception):
    """Parser Error"""


class URLParserError(ParserError):
    """Pub Date Error"""


class ArticleCreationError(ScraperError):
    """Error during Article object creation from HTML"""
