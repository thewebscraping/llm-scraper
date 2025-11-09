"""
Demo XPath Selector Feature
============================

This script demonstrates the new XPath selector support alongside CSS selectors.
"""

from bs4 import BeautifulSoup
from llm_scraper import ElementSelector, ParserConfig, SelectorType
from llm_scraper.parsers.base import BaseParser


# Sample HTML
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Tech News</title>
</head>
<body>
    <article class="post" data-type="article" data-id="12345">
        <header>
            <h1 class="post-title">Understanding XPath in Web Scraping</h1>
            <div class="meta">
                <time datetime="2024-01-15T10:00:00Z" pubdate>January 15, 2024</time>
                <div class="byline">
                    <span>Authors:</span>
                    <a href="/author/alice" rel="author">Alice Johnson</a>
                    <a href="/author/bob" rel="author">Bob Smith</a>
                </div>
            </div>
        </header>
        
        <div class="content">
            <p>XPath provides powerful element selection capabilities.</p>
            <p class="highlight">Important: XPath can navigate the DOM tree flexibly.</p>
            <p>This makes it ideal for complex scraping tasks.</p>
        </div>
        
        <footer>
            <div class="tags">
                <a href="/tag/web-scraping" rel="tag">Web Scraping</a>
                <a href="/tag/xpath" rel="tag">XPath</a>
                <a href="/tag/python" rel="tag">Python</a>
            </div>
        </footer>
    </article>
</body>
</html>
"""


def demo_css_selector():
    """Demo 1: Traditional CSS selector"""
    print("\n" + "="*70)
    print("DEMO 1: Traditional CSS Selector")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    selector = ElementSelector(
        selector="h1.post-title",
        type="text"
    )
    parser = BaseParser(soup, ParserConfig(domain="demo", content=selector))
    result = parser._extract_element(selector)
    
    print(f"Selector: h1.post-title")
    print(f"Result: {result}\n")


def demo_xpath_selector():
    """Demo 2: XPath expression"""
    print("="*70)
    print("DEMO 2: XPath Expression")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    selector = ElementSelector(
        selector="//h1[@class='post-title']",
        type="text"
    )
    parser = BaseParser(soup, ParserConfig(domain="demo", content=selector))
    result = parser._extract_element(selector)
    
    print(f"Selector: //h1[@class='post-title']")
    print(f"Result: {result}\n")


def demo_xpath_position():
    """Demo 3: XPath position-based selection"""
    print("="*70)
    print("DEMO 3: XPath Position-Based Selection")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    selector = ElementSelector(
        selector="//div[@class='content']//p[2]",
        type="text"
    )
    parser = BaseParser(soup, ParserConfig(domain="demo", content=selector))
    result = parser._extract_element(selector)
    
    print(f"Selector: //div[@class='content']//p[2]")
    print(f"Result: {result}\n")


def demo_xpath_text_contains():
    """Demo 4: XPath with text content matching"""
    print("="*70)
    print("DEMO 4: XPath Text Content Matching")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    selector = ElementSelector(
        selector="//p[contains(text(), 'Important:')]",
        type="text"
    )
    parser = BaseParser(soup, ParserConfig(domain="demo", content=selector))
    result = parser._extract_element(selector)
    
    print(f"Selector: //p[contains(text(), 'Important:')]")
    print(f"Result: {result}\n")


def demo_mixed_fallback():
    """Demo 5: Mixed CSS and XPath fallback chain"""
    print("="*70)
    print("DEMO 5: Mixed CSS + XPath Fallback Chain")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    selector = ElementSelector(
        selector=[
            "h2.missing",                          # CSS (will fail)
            "//h1[@class='post-title']",          # XPath (will succeed)
            "h1"                                   # CSS fallback
        ],
        type="text"
    )
    parser = BaseParser(soup, ParserConfig(domain="demo", content=selector))
    result = parser._extract_element(selector)
    
    print("Selectors (fallback chain):")
    print("  1. h2.missing (CSS)")
    print("  2. //h1[@class='post-title'] (XPath) ← matched!")
    print("  3. h1 (CSS)")
    print(f"Result: {result}\n")


def demo_xpath_parent_scope():
    """Demo 6: XPath with parent scoping"""
    print("="*70)
    print("DEMO 6: XPath with Parent Scoping")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    selector = ElementSelector(
        selector=[{
            "query": ".//a[@rel='author']",
            "selector_type": "xpath",
            "parent": "//div[@class='byline']"
        }],
        type="text",
        all=True
    )
    parser = BaseParser(soup, ParserConfig(domain="demo", content=selector))
    result = parser._extract_element(selector)
    
    print("Parent: //div[@class='byline']")
    print("Query: .//a[@rel='author']")
    print(f"Results: {result}\n")


def demo_xpath_attribute_extraction():
    """Demo 7: XPath with attribute extraction"""
    print("="*70)
    print("DEMO 7: XPath Attribute Extraction")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    selector = ElementSelector(
        selector="//time[@pubdate]",
        type="text",
        attribute="datetime"
    )
    parser = BaseParser(soup, ParserConfig(domain="demo", content=selector))
    result = parser._extract_element(selector)
    
    print("Selector: //time[@pubdate]")
    print("Attribute: datetime")
    print(f"Result: {result}\n")


def demo_xpath_boolean_logic():
    """Demo 8: XPath with boolean logic"""
    print("="*70)
    print("DEMO 8: XPath Boolean Logic")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    selector = ElementSelector(
        selector="//article[@class='post' and @data-type='article']",
        type="text",
        attribute="data-id"
    )
    parser = BaseParser(soup, ParserConfig(domain="demo", content=selector))
    result = parser._extract_element(selector)
    
    print("Selector: //article[@class='post' and @data-type='article']")
    print("Attribute: data-id")
    print(f"Result: {result}\n")


def demo_full_config():
    """Demo 9: Complete ParserConfig with mixed selectors"""
    print("="*70)
    print("DEMO 9: Complete ParserConfig with Mixed Selectors")
    print("="*70)
    
    soup = BeautifulSoup(HTML, "lxml")
    
    config = ParserConfig(
        domain="demo",
        title=ElementSelector(
            selector=["h1.post-title", "//h1"],
            type="text"
        ),
        content=ElementSelector(
            selector=["div.content", "//div[@class='content']"],
            type="html"
        ),
        authors=ElementSelector(
            selector=[{
                "query": ".//a[@rel='author']",
                "selector_type": "xpath",
                "parent": "//div[@class='byline']"
            }],
            type="text",
            all=True
        ),
        date_published=ElementSelector(
            selector=[
                {"query": "time", "selector_type": "css", "attribute": "datetime"},
                {"query": "//time[@pubdate]", "selector_type": "xpath", "attribute": "datetime"}
            ],
            type="text"
        ),
        tags=ElementSelector(
            selector=[
                {"query": ".//a", "selector_type": "xpath", "parent": "//div[@class='tags']"},
                "a[rel='tag']"
            ],
            type="text",
            all=True
        )
    )
    
    parser = BaseParser(soup, config)
    data = parser.parse()
    
    print("Extracted Data:")
    print(f"  Title: {data.get('title')}")
    print(f"  Authors: {data.get('authors')}")
    print(f"  Date: {data.get('date_published')}")
    print(f"  Tags: {data.get('tags')}")
    print(f"  Content length: {len(data.get('content', ''))} characters\n")


def main():
    """Run all demos"""
    print("\n" + "🚀 XPath Selector Feature Demonstrations".center(70, " "))
    
    demo_css_selector()
    demo_xpath_selector()
    demo_xpath_position()
    demo_xpath_text_contains()
    demo_mixed_fallback()
    demo_xpath_parent_scope()
    demo_xpath_attribute_extraction()
    demo_xpath_boolean_logic()
    demo_full_config()
    
    print("="*70)
    print("✅ All demos completed successfully!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
