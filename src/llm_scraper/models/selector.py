"""
Selector Models for HTML Extraction
====================================

This module defines the configuration models for extracting structured data from HTML pages.

Architecture Overview:
======================

1. SelectorConfig - Per-selector configuration
   - Defines a single CSS selector with optional attribute and parent scope
   - Used in advanced selector lists for fine-grained control

2. ElementSelector - Field extraction configuration  
   - Defines how to extract a single field (title, content, authors, etc.)
   - Supports multiple selector formats:
     * Simple string: "h1.title"
     * Fallback list: ["h1.title", "h1", ".title"]
     * Config objects: [{"selector": "time", "attribute": "datetime"}]

3. ParserConfig - Domain-specific configuration
   - Complete extraction configuration for a specific domain
   - Contains all field selectors + metadata (domain, lang, type)
   - Stored as JSON files in parsers/configs/{lang}/{char}/{domain}.json


Key Features:
=============

✓ Fallback Chain: Try multiple selectors until one matches
✓ Per-Selector Attributes: Each selector can extract different attributes
✓ Parent Scoping: Search within specific parent elements
✓ Multiple Return: Extract single value or list of values (all=true)
✓ Type Control: Extract text, HTML, or attribute values


How It Works:
=============

Step 1: Define ParserConfig (JSON)
{
    "domain": "example.com",
    "content": {"css_selector": "article", "type": "html"},
    "authors": {
        "css_selector": [
            {"selector": "a", "parent": ".byline"},
            ".author"
        ],
        "type": "text",
        "all": true
    }
}

Step 2: BaseParser processes each ElementSelector
- Tries selectors in order (fallback chain)
- Applies parent scope if specified
- Extracts attribute/text/html based on type
- Returns single value or list based on all flag

Step 3: Article.from_html() merges extracted data
- Combines parser config data + meta tags
- Priority: parser config > meta tags > defaults


Parent Selector Deep Dive:
===========================

Without parent (searches entire page):
HTML:
  <nav><a href="/about">About</a></nav>
  <article>
    <div class="byline"><a href="/author/john">John</a></div>
  </article>

Selector: {"selector": "a", "attribute": "href"}
Result: "/about" (first <a> found - WRONG!)

With parent (scoped search):
Selector: {
    "selector": "a", 
    "attribute": "href",
    "parent": ".byline"
}
Result: "/author/john" (correct author link!)

Flow:
1. Find parent: soup.select_one(".byline") -> <div class="byline">
2. Search within parent: parent.select_one("a") -> <a href="/author/john">
3. Extract attribute: href="/author/john"


Advanced Examples:
==================

Example 1: Date extraction with fallbacks
{
    "date_published": {
        "css_selector": [
            {"selector": "time", "attribute": "datetime"},
            {"selector": "meta[property='article:published_time']", "attribute": "content"},
            ".publish-date"
        ],
        "type": "text"
    }
}

Example 2: Tags from multiple sources
{
    "tags": {
        "css_selector": [
            "a[href*='/tags/']",
            {"selector": "a", "parent": ".post-tags"},
            "a[rel='tag']"
        ],
        "type": "text",
        "all": true
    }
}

Example 3: Follow URLs with parent scope
{
    "follow_urls": {
        "css_selector": [
            {"selector": "a", "attribute": "href", "parent": ".related-posts"},
            {"selector": "a", "attribute": "href", "parent": ".editors-picks"}
        ],
        "type": "text",
        "all": true
    }
}
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class SelectorConfig(BaseModel):
    """
    Configuration for an individual CSS selector with per-selector options.
    
    This allows fine-grained control for each selector in a list, enabling:
    - Custom attribute extraction per selector
    - Parent-scoped searching (find parent first, then search within it)
    
    Examples:
        Simple selector with attribute:
        {
            "selector": "time",
            "attribute": "datetime"
        }
        
        Selector within parent scope:
        {
            "selector": "a",
            "attribute": "href",
            "parent": ".post-meta"
        }
        # This finds <div class="post-meta"> first, then searches for <a> inside it
    """
    selector: str = Field(description="The CSS selector string.")
    attribute: Optional[str] = Field(
        default=None, 
        description="Specific attribute to extract for this selector (e.g., 'href', 'datetime', 'src')."
    )
    parent: Optional[str] = Field(
        default=None, 
        description="Parent element selector - finds parent first, then searches for 'selector' within it. "
                    "Useful for scoping searches to specific sections of the page."
    )


class ElementSelector(BaseModel):
    """
    A declarative model to specify how to extract data from HTML with flexible selector syntax.
    
    Selector Format Support:
    ========================
    
    1. Simple String Selector
    --------------------------
    "div.content"
    - Finds first <div class="content"> element
    
    2. Array of String Selectors (Fallback Chain)
    ----------------------------------------------
    ["div.content", "article", "main"]
    - Tries each selector in order
    - Returns first match found
    - Useful for sites with varying HTML structure
    
    3. Array of Selector Config Objects (Advanced)
    -----------------------------------------------
    [
        {"selector": "time", "attribute": "datetime"},
        {"selector": ".published-date", "parent": ".post-meta"}
    ]
    - Each selector can have its own attribute and parent scope
    - Allows mixing simple and complex selectors
    
    
    Examples:
    =========
    
    # Extract text from title
    {
        "css_selector": "h1.article-title",
        "type": "text"
    }
    
    # Extract datetime attribute with fallbacks
    {
        "css_selector": [
            {"selector": "time", "attribute": "datetime"},
            {"selector": "meta[property='article:published_time']", "attribute": "content"}
        ],
        "type": "text"
    }
    
    # Extract all tags within a parent container
    {
        "css_selector": [
            {"selector": "a", "parent": ".tags-container"},
            "a.tag",
            "a[rel='tag']"
        ],
        "type": "text",
        "all": true
    }
    
    # Extract HTML content
    {
        "css_selector": "div.article-body",
        "type": "html"
    }
    
    
    Parent Selector Use Cases:
    ==========================
    
    When to use 'parent':
    - To scope search to specific page sections
    - To avoid false matches from navigation/sidebar/footer
    - To extract from repeating structures (e.g., comments, items)
    
    Example HTML:
    <div class="post-meta">
        <a href="/author/john">John Doe</a>
    </div>
    <footer>
        <a href="/about">About</a>
    </footer>
    
    Selector:
    {
        "selector": "a",
        "attribute": "href",
        "parent": ".post-meta"
    }
    Result: "/author/john" (not "/about")
    """

    css_selector: Union[str, List[Union[str, Dict[str, Any]]]] = Field(
        description="CSS selector(s) - can be:\n"
                    "- String: 'div.content'\n"
                    "- List of strings: ['div.content', 'article']\n"
                    "- List of config objects: [{'selector': 'time', 'attribute': 'datetime'}]"
    )
    type: Literal["text", "html", "attribute"] = Field(
        default="text", 
        description="The type of data to extract:\n"
                    "- 'text': Extract text content (default)\n"
                    "- 'html': Extract HTML including tags\n"
                    "- 'attribute': Extract attribute value (requires 'attribute' field)"
    )
    attribute: Optional[str] = Field(
        default=None, 
        description="Default attribute name to extract (e.g., 'href', 'src', 'datetime'). "
                    "Can be overridden per selector in config objects."
    )
    all: bool = Field(
        default=False, 
        description="If true, find all matching elements and return a list. "
                    "If false, return only the first match."
    )


class ParserConfig(BaseModel):
    """
    A configuration model that defines all the selectors needed to parse a specific domain's article pages.
    
    This is the main configuration file for domain-specific HTML extraction.
    Each domain should have its own ParserConfig JSON file.
    
    Required Fields:
    ================
    - domain: The domain this config is for (e.g., "example.com")
    - content: ElementSelector for main article content (REQUIRED)
    
    Optional Fields:
    ================
    - title, description, authors, date_published, date_modified
    - tags, topics: For categorization
    - follow_urls: Links to discover more articles
    - cleanup: CSS selectors to remove before parsing
    - sitemaps, rss_feeds: For discovery
    
    
    Complete Example:
    =================
    
    {
        "domain": "techblog.com",
        "lang": "en",
        "type": "article",
        
        "title": {
            "css_selector": ["h1.post-title", "h1"],
            "type": "text"
        },
        
        "description": {
            "css_selector": ".post-excerpt",
            "type": "text"
        },
        
        "content": {
            "css_selector": [".post-content", "article"],
            "type": "html"
        },
        
        "authors": {
            "css_selector": [
                {"selector": "a", "parent": ".author-info"},
                ".author-name"
            ],
            "type": "text",
            "all": true
        },
        
        "date_published": {
            "css_selector": [
                {"selector": "time", "attribute": "datetime"},
                {"selector": "meta[property='article:published_time']", "attribute": "content"}
            ],
            "type": "text"
        },
        
        "tags": {
            "css_selector": [
                {"selector": "a", "parent": ".tags"},
                "a.tag"
            ],
            "type": "text",
            "all": true
        },
        
        "follow_urls": {
            "css_selector": ".related-posts a",
            "type": "text",
            "attribute": "href",
            "all": true
        },
        
        "cleanup": [
            ".ads",
            ".newsletter-signup",
            ".related-posts",
            ".comments"
        ],
        
        "sitemaps": [
            "https://techblog.com/sitemap.xml"
        ],
        
        "rss_feeds": [
            "https://techblog.com/feed.rss"
        ]
    }
    
    
    Real-World Use Cases:
    =====================
    
    1. Date with Fallback Chain:
    {
        "date_published": {
            "css_selector": [
                {"selector": "time", "attribute": "datetime"},
                {"selector": ".publish-date"},
                {"selector": "meta[property='article:published_time']", "attribute": "content"}
            ],
            "type": "text"
        }
    }
    
    2. Authors Scoped to Container:
    {
        "authors": {
            "css_selector": [
                {"selector": "a", "attribute": "href", "parent": ".byline"},
                ".author-link"
            ],
            "type": "text",
            "all": true
        }
    }
    
    3. Tags with Multiple Sources:
    {
        "tags": {
            "css_selector": [
                "a[href*='/tags/']",
                {"selector": "a", "parent": ".post-tags"},
                "a[rel='tag']"
            ],
            "type": "text",
            "all": true
        }
    }
    """

    domain: str = Field(description="The domain this configuration is for, e.g., 'example.com'.")
    lang: str = Field(default="en", description="Language code for this configuration (e.g., 'en', 'vi').")
    type: str = Field(default="article", description="Content type (e.g., 'article', 'blog').")
    
    title: Optional[ElementSelector] = None
    description: Optional[ElementSelector] = None
    content: ElementSelector
    authors: Optional[ElementSelector] = None
    date_published: Optional[ElementSelector] = None
    date_modified: Optional[ElementSelector] = None
    tags: Optional[ElementSelector] = None
    topics: Optional[ElementSelector] = None
    follow_urls: Optional[ElementSelector] = None

    # A list of selectors for elements to remove before parsing.
    cleanup: List[str] = Field(default_factory=list, description="List of CSS selectors to remove before parsing.")

    # Lists for discovery
    sitemaps: List[str] = Field(default_factory=list, description="A list of sitemap URLs.")
    rss_feeds: List[str] = Field(default_factory=list, description="A list of RSS feed URLs.")

    class Config:
        frozen = True
        title = "Parser Configuration"
        json_schema_extra = {
            "example": {
                "domain": "example.com",
                "lang": "en",
                "type": "article",
                "title": {
                    "css_selector": ["h1.article-title", "h1"],
                    "type": "text"
                },
                "content": {
                    "css_selector": ["div.article-body", "article"],
                    "type": "html"
                },
                "authors": {
                    "css_selector": [
                        {"selector": "a", "parent": ".author-info"},
                        ".author-name"
                    ],
                    "type": "text",
                    "all": True
                },
                "date_published": {
                    "css_selector": [
                        {"selector": "time", "attribute": "datetime"},
                        ".publish-date"
                    ],
                    "type": "text"
                },
                "tags": {
                    "css_selector": [
                        {"selector": "a", "parent": ".tags"},
                        "a.tag"
                    ],
                    "type": "text",
                    "all": True
                },
                "cleanup": [
                    "div.ads", 
                    "figure.related-articles",
                    ".newsletter-signup"
                ],
                "sitemaps": ["https://example.com/sitemap_articles.xml"],
                "rss_feeds": ["https://example.com/feed.rss"],
            }
        }