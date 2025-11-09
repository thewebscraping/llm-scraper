"""
Selector Models for HTML Extraction with CSS and XPath Support
=================================================================

This module defines configuration models for extracting structured data from HTML
using both CSS selectors and XPath expressions.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class SelectorType(str, Enum):
    """
    Type of selector to use for element extraction.
    
    - CSS: Standard CSS selector (e.g., "div.content", "#main > p")
    - XPATH: XPath expression (e.g., "//div[@class='content']", "//p[1]")
    - AUTO: Automatically detect based on query syntax (starts with // or / = XPath, else CSS)
    """
    CSS = "css"
    XPATH = "xpath"
    AUTO = "auto"


class SelectorConfig(BaseModel):
    """
    Configuration for an individual selector with fine-grained options.
    
    Supports both CSS selectors and XPath expressions.
    """
    query: str = Field(description="The selector query string (CSS selector or XPath expression).")
    selector_type: SelectorType = Field(
        default=SelectorType.AUTO,
        description="Type of selector: 'css', 'xpath', or 'auto' (auto-detect based on query syntax)."
    )
    attribute: Optional[str] = Field(
        default=None, 
        description="Specific attribute to extract (e.g., 'href', 'datetime', 'src')."
    )
    parent: Optional[str] = Field(
        default=None, 
        description="Parent element selector - finds parent first, then searches within it."
    )


class ElementSelector(BaseModel):
    """
    Declarative model for HTML data extraction with CSS and XPath support.
    
    Supports mixing CSS selectors and XPath expressions in fallback chains.
    Each selector can have its own cleanup rules for targeted element removal.
    """
    selector: Union[str, List[Union[str, Dict[str, Any]]]] = Field(
        description="Selector(s) - can be:\n"
                    "- String: 'div.content' (CSS) or '//div[@class=\"content\"]' (XPath)\n"
                    "- List of strings: ['div.content', '//article', 'main']\n"
                    "- List of config objects with 'query', 'selector_type', etc."
    )
    type: Literal["text", "html", "attribute"] = Field(
        default="text", 
        description="Data extraction type: 'text', 'html', or 'attribute'"
    )
    attribute: Optional[str] = Field(
        default=None, 
        description="Default attribute name to extract (can be overridden per selector)"
    )
    all: bool = Field(
        default=False, 
        description="If true, find all matching elements and return a list"
    )
    cleanup: Optional[List[str]] = Field(
        default=None,
        description="CSS/XPath selectors to remove from extracted element before processing. "
                    "Useful for content field to remove ads, related posts, etc."
    )


class ParserConfig(BaseModel):
    """Complete extraction configuration for a specific domain.

    NOTE: Field declaration order controls extraction order in `BaseParser.parse()`.
    The `content` field is intentionally declared LAST among extraction targets so
    that other metadata (e.g. `main_points`, `tags`, `follow_urls`) can be
    extracted from the original DOM before any heavy per-field cleanup tied to
    the `content` selector mutates nested elements.
    """
    domain: str = Field(description="The domain this configuration is for")
    lang: str = Field(default="en", description="Language code")
    type: str = Field(default="article", description="Content type")

    # Extraction fields (ordered; modify with care)
    title: Optional[ElementSelector] = None
    description: Optional[ElementSelector] = None
    authors: Optional[ElementSelector] = None
    date_published: Optional[ElementSelector] = None
    date_modified: Optional[ElementSelector] = None
    tags: Optional[ElementSelector] = None
    topics: Optional[ElementSelector] = None
    main_points: Optional[ElementSelector] = None
    follow_urls: Optional[ElementSelector] = None
    # Content LAST so it doesn't remove nodes needed by earlier extractions
    content: ElementSelector

    # Global (pre-parse) cleanup selectors & discovery sources
    cleanup: List[str] = Field(
        default_factory=list,
        description="Global CSS/XPath selectors removed pre-parse (runs before field extraction)."
    )
    sitemaps: List[str] = Field(default_factory=list)
    rss_feeds: List[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True, title="Parser Configuration")
