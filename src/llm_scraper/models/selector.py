from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ElementSelector(BaseModel):
    """
    A declarative model to specify how to extract a piece of data from HTML.
    It can accept a single CSS selector or a list of selectors to try in order.
    """

    css_selector: Union[str, List[str]] = Field(description="A CSS selector or a list of CSS selectors to find the element(s).")
    type: Literal["text", "html", "attribute"] = Field(
        default="text", description="The type of data to extract: 'text', 'html', or an 'attribute'."
    )
    attribute: Optional[str] = Field(
        default=None, description="If type is 'attribute', this is the name of the attribute to extract."
    )
    all: bool = Field(
        default=False, description="If true, find all matching elements and return a list. If false, return the first match."
    )


class ParserConfig(BaseModel):
    """
    A configuration model that defines all the selectors needed to parse a specific
    type of article page.
    """

    title: Optional[ElementSelector] = None
    description: Optional[ElementSelector] = None
    content: ElementSelector
    author: Optional[ElementSelector] = None
    date_published: Optional[ElementSelector] = None
    date_modified: Optional[ElementSelector] = None
    tags: Optional[ElementSelector] = None
    topics: Optional[ElementSelector] = None

    # A list of selectors for elements to remove before parsing.
    cleanup: List[str] = Field(default_factory=list, description="List of CSS selectors to remove before parsing.")

    # Manual lists for discovery
    manual_sitemaps: List[str] = Field(default_factory=list, description="A list of manually specified sitemap URLs.")
    manual_rss_feeds: List[str] = Field(default_factory=list, description="A list of manually specified RSS feed URLs.")

    # The domain this config applies to
    domain: str = Field(description="The domain this configuration is for, e.g., 'example.com'.")

    class Config:
        frozen = True
        title = "Parser Configuration"
        json_schema_extra = {
            "example": {
                "domain": "example.com",
                "title": {
                    "css_selector": "h1.article-title",
                },
                "content": {
                    "css_selector": "div.article-body",
                },
                "tags": {
                    "css_selector": "a.tag",
                    "all": True,
                },
                "cleanup": ["div.ads", "figure.related-articles"],
                "manual_sitemaps": ["https://example.com/sitemap_articles.xml"],
                "manual_rss_feeds": ["https://example.com/feed.rss"],
            }
        }