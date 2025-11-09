"""
Test XPath selector support alongside CSS selectors.

This test demonstrates:
1. Pure CSS selectors
2. Pure XPath expressions
3. Mixed CSS and XPath in fallback chains
4. Parent scoping with both CSS and XPath
5. Auto-detection of selector type
"""
import pytest
from bs4 import BeautifulSoup

from llm_scraper.models.selector import ElementSelector, ParserConfig, SelectorType
from llm_scraper.parsers.base import BaseParser


# Sample HTML for testing
HTML_SAMPLE = """
<!DOCTYPE html>
<html>
<head>
    <meta property="og:title" content="Test Article">
    <meta property="article:published_time" content="2024-01-15T10:00:00Z">
</head>
<body>
    <article class="post" data-type="article">
        <header class="post-header">
            <h1 class="post-title">Understanding XPath and CSS Selectors</h1>
            <div class="post-meta">
                <time datetime="2024-01-15T10:00:00Z" class="published">January 15, 2024</time>
                <div class="byline">
                    <span>By:</span>
                    <a href="/author/john" class="author" rel="author">John Doe</a>
                    <a href="/author/jane" class="author" rel="author">Jane Smith</a>
                </div>
            </div>
        </header>
        
        <div class="post-content">
            <p>This article demonstrates both CSS and XPath selectors.</p>
            <p>XPath provides more powerful element selection capabilities.</p>
            <p class="highlight">Important: XPath can navigate the DOM tree more flexibly.</p>
        </div>
        
        <footer class="post-footer">
            <div class="tags">
                <a href="/tag/web-scraping" rel="tag">Web Scraping</a>
                <a href="/tag/xpath" rel="tag">XPath</a>
                <a href="/tag/css" rel="tag">CSS</a>
            </div>
            <div class="related">
                <h3>Related Articles</h3>
                <ul>
                    <li><a href="/article/css-basics">CSS Basics</a></li>
                    <li><a href="/article/xpath-guide">XPath Guide</a></li>
                </ul>
            </div>
        </footer>
    </article>
    
    <aside class="sidebar">
        <a href="/about">About Us</a>
        <a href="/contact">Contact</a>
    </aside>
</body>
</html>
"""


class TestCSSSelectors:
    """Test pure CSS selector functionality."""
    
    def test_simple_css_selector(self):
        """Test basic CSS selector."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        config = ParserConfig(
            domain="example.com",
            content=ElementSelector(selector="div.post-content", type="html")
        )
        parser = BaseParser(soup, config)
        result = parser._extract_element(config.content)
        
        assert result is not None
        assert "XPath provides more powerful" in result
    
    def test_css_with_attribute(self):
        """Test CSS selector with attribute extraction."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector="time.published",
            type="text",
            attribute="datetime"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert result == "2024-01-15T10:00:00Z"
    
    def test_css_with_parent_scope(self):
        """Test CSS selector with parent scoping."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector=[{
                "query": "a",
                "selector_type": "css",
                "attribute": "href",
                "parent": ".byline"
            }],
            type="text",
            all=True
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert "/author/john" in result
        assert "/author/jane" in result
    
    def test_css_fallback_chain(self):
        """Test CSS selector fallback chain."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector=["h2.title", "h1.post-title", "h1"],
            type="text"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert result == "Understanding XPath and CSS Selectors"


class TestXPathSelectors:
    """Test pure XPath selector functionality."""
    
    def test_simple_xpath_selector(self):
        """Test basic XPath expression."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector="//h1[@class='post-title']",
            type="text"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert result == "Understanding XPath and CSS Selectors"
    
    def test_xpath_with_attribute(self):
        """Test XPath with attribute extraction."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector="//time[@class='published']",
            type="text",
            attribute="datetime"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert result == "2024-01-15T10:00:00Z"
    
    def test_xpath_position_based(self):
        """Test XPath position-based selection."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        # Use simpler position-based XPath without parentheses at start
        selector = ElementSelector(
            selector="//div[@class='post-content']//p[1]",
            type="text"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert result is not None
        assert "demonstrates both CSS and XPath" in result
    
    def test_xpath_attribute_filtering(self):
        """Test XPath with attribute filtering."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector="//a[@rel='author']",
            type="text",
            all=True
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert "John Doe" in result
        assert "Jane Smith" in result
    
    def test_xpath_with_parent_scope(self):
        """Test XPath with parent scoping."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector=[{
                "query": ".//a[@rel='author']",
                "selector_type": "xpath",
                "parent": "//div[@class='byline']"
            }],
            type="text",
            all=True
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert "John Doe" in result
    
    def test_xpath_text_contains(self):
        """Test XPath with text content matching."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector="//p[contains(@class, 'highlight')]",
            type="text"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert "Important:" in result
        assert "XPath can navigate" in result


class TestMixedSelectors:
    """Test mixing CSS and XPath selectors in fallback chains."""
    
    def test_css_then_xpath_fallback(self):
        """Test fallback from CSS to XPath."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector=[
                "h2.missing-class",  # CSS - will fail
                "//h1[@class='post-title']",  # XPath - will succeed
                "h1"  # CSS fallback
            ],
            type="text"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert result == "Understanding XPath and CSS Selectors"
    
    def test_xpath_then_css_fallback(self):
        """Test fallback from XPath to CSS."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector=[
                "//h2[@class='missing']",  # XPath - will fail
                "h1.post-title"  # CSS - will succeed
            ],
            type="text"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert result == "Understanding XPath and CSS Selectors"
    
    def test_mixed_with_configs(self):
        """Test mixed selectors with config objects."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector=[
                {"query": "time.missing", "selector_type": "css", "attribute": "datetime"},
                {"query": "//time[@class='published']", "selector_type": "xpath", "attribute": "datetime"},
                {"query": "meta[property='article:published_time']", "attribute": "content"}
            ],
            type="text"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert result == "2024-01-15T10:00:00Z"
    
    def test_auto_detection(self):
        """Test automatic detection of CSS vs XPath."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        
        # Test auto-detection of XPath (starts with //)
        selector_xpath = ElementSelector(
            selector="//h1[@class='post-title']",
            type="text"
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector_xpath))
        result_xpath = parser._extract_element(selector_xpath)
        
        # Test auto-detection of CSS (doesn't start with /)
        selector_css = ElementSelector(
            selector="h1.post-title",
            type="text"
        )
        result_css = parser._extract_element(selector_css)
        
        assert result_xpath == result_css == "Understanding XPath and CSS Selectors"


class TestComplexScenarios:
    """Test complex real-world scenarios."""
    
    def test_extract_tags_multiple_methods(self):
        """Test extracting tags using both CSS and XPath."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector=[
                {"query": ".//a", "selector_type": "xpath", "parent": "//div[@class='tags']"},
                "a[rel='tag']",
                "//a[@rel='tag']"
            ],
            type="text",
            all=True
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert isinstance(result, list)
        assert len(result) == 3
        assert "Web Scraping" in result
        assert "XPath" in result
        assert "CSS" in result
    
    def test_extract_related_links(self):
        """Test extracting related article links."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        selector = ElementSelector(
            selector=[
                {"query": ".//a", "selector_type": "xpath", "parent": "//div[@class='related']", "attribute": "href"},
                ".related a"
            ],
            type="text",
            attribute="href",
            all=True
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector))
        result = parser._extract_element(selector)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert "/article/css-basics" in result
        assert "/article/xpath-guide" in result
    
    def test_avoid_sidebar_links(self):
        """Test that parent scoping avoids extracting sidebar links."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        
        # Without parent scope - will get sidebar links too
        selector_all = ElementSelector(
            selector="a",
            type="text",
            attribute="href",
            all=True
        )
        parser = BaseParser(soup, ParserConfig(domain="test.com", content=selector_all))
        result_all = parser._extract_element(selector_all)
        assert "/about" in result_all or "/contact" in result_all
        
        # With parent scope - only byline links
        selector_scoped = ElementSelector(
            selector=[{
                "query": "a",
                "selector_type": "css",
                "attribute": "href",
                "parent": ".byline"
            }],
            type="text",
            all=True
        )
        result_scoped = parser._extract_element(selector_scoped)
        assert "/about" not in result_scoped
        assert "/author/john" in result_scoped
    
    def test_full_parser_config(self):
        """Test complete ParserConfig with mixed selectors."""
        soup = BeautifulSoup(HTML_SAMPLE, "lxml")
        
        config = ParserConfig(
            domain="example.com",
            lang="en",
            type="article",
            title=ElementSelector(
                selector=["h1.post-title", "//h1[@class='post-title']"],
                type="text"
            ),
            content=ElementSelector(
                selector=["div.post-content", "//div[@class='post-content']"],
                type="html"
            ),
            authors=ElementSelector(
                selector=[
                    {"query": ".//a[@rel='author']", "selector_type": "xpath", "parent": "//div[@class='byline']"},
                    {"query": "a.author", "selector_type": "css", "parent": ".byline"}
                ],
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
        
        assert data["title"] == "Understanding XPath and CSS Selectors"
        assert "XPath provides more powerful" in data["content"]
        assert len(data["authors"]) == 2
        assert "John Doe" in data["authors"]
        assert data["date_published"] == "2024-01-15T10:00:00Z"
        assert len(data["tags"]) == 3
        assert "XPath" in data["tags"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
