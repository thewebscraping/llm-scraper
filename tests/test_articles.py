import pytest
from datetime import datetime
from llm_scraper.articles import Article, Provenance
from llm_scraper.exceptions import ArticleCreationError

# Sample HTML with meta and schema data
SAMPLE_HTML = """
<html>
<head>
    <title>Test Article Title</title>
    <meta property="og:title" content="OpenGraph Title" />
    <meta name="description" content="Meta Description" />
    <meta property="article:published_time" content="2023-01-01T12:00:00Z" />
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      "headline": "Schema Headline",
      "datePublished": "2023-01-02T12:00:00Z",
      "description": "Schema Description"
    }
    </script>
</head>
<body>
    <h1>Main Heading</h1>
    <p>This is the first paragraph of the article.</p>
    <p>This is the second paragraph, with more content.</p>
</body>
</html>
"""

def test_from_html_successful_creation():
    """Tests that an Article can be successfully created from HTML."""
    url = "https://example.com/test-article"
    article = Article.from_html(SAMPLE_HTML, url)

    assert isinstance(article, Article)
    assert article.title == "OpenGraph Title"  # Meta helper should take priority
    assert article.description == "Meta Description"
    assert article.metadata.published_at == datetime(2023, 1, 1, 12, 0) # From meta
    assert "This is the first paragraph" in article.content
    assert article.provenance.source_url == url

def test_from_html_metadata_fallback():
    """Tests that schema metadata is used when meta tags are missing."""
    html_no_meta = """
    <html>
    <head>
        <title>Test Title</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "NewsArticle",
          "headline": "Schema Headline",
          "datePublished": "2023-01-02T12:00:00Z"
        }
        </script>
    </head>
    <body><p>Content</p></body>
    </html>
    """
    url = "https://example.com/no-meta"
    article = Article.from_html(html_no_meta, url)

    assert article.title == "Schema Headline"
    assert article.metadata.published_at == datetime(2023, 1, 2, 12, 0)

def test_from_html_with_invalid_html():
    """Tests that ArticleCreationError is raised for invalid or empty HTML."""
    with pytest.raises(ArticleCreationError, match="Cannot create article from empty or invalid HTML."):
        Article.from_html("", "https://example.com/empty")

    with pytest.raises(ArticleCreationError, match="Failed to extract meaningful content from HTML."):
        Article.from_html("<html><body></body></html>", "https://example.com/no-content")

    with pytest.raises(ArticleCreationError, match="Failed to extract meaningful content from HTML."):
        Article.from_html("just some text without html structure", "https://example.com/invalid")

def test_content_extraction_logic():
    """Tests the improved content extraction logic."""
    html = """
    <html>
        <head><title>Title</title></head>
        <body>
            <header><h1>This is a header</h1></header>
            <nav><a>Home</a></nav>
            <main>
                <article>
                    <h2>Article Title</h2>
                    <p>First paragraph.</p>
                    <p>Second paragraph.</p>
                </article>
            </main>
            <footer><p>Copyright</p></footer>
        </body>
    </html>
    """
    url = "https://example.com/main-content"
    article = Article.from_html(html, url)

    assert "First paragraph." in article.content
    assert "Second paragraph." in article.content
    assert "This is a header" not in article.content # Should be excluded
    assert "Copyright" not in article.content # Should be excluded
