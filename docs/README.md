# LLM Scraper Documentation

Complete documentation for the LLM Scraper library.

## 📚 Documentation Index

### Getting Started
- [Quick Start Guide](#quick-start) - Get up and running in 5 minutes
- [Installation](#installation) - Installation instructions
- [Basic Usage](#basic-usage) - Simple examples

### Core Concepts
- **[Selector Guide](SELECTOR_GUIDE.md)** - Complete guide to creating parser configurations
  - Selector syntax and formats
  - Parent scoping
  - Real-world examples
  - Testing and troubleshooting

### API Reference
- **[Article Architecture Guide](ARTICLES_GUIDE_EN.md)** - Complete article module architecture (English)
- **[Hướng Dẫn Kiến Trúc Article](ARTICLES_GUIDE_VI.md)** - Kiến trúc module article (Tiếng Việt)
- [Article Model](API_ARTICLE.md) - Article schema and methods
- [Parser Configuration](API_PARSER.md) - ParserConfig reference
- [Metadata Extraction](API_METADATA.md) - Meta tags and Schema.org
 - Bulk Scraping & Pagination (summary): Sitemap/RSS modes now run asynchronously and return `task_id`; paginate results via `/scrapes/{task_id}` (limit <= 50). Article bodies are fetched individually using `/article/{id}`. Bulk modes require `X-System-Key` if `SYSTEM_SCRAPE_SECRET` is set.

### Guides
- [Creating Domain Configs](GUIDE_DOMAIN_CONFIG.md) - Step-by-step config creation
- [Testing Configurations](GUIDE_TESTING.md) - How to test your configs
- [Best Practices](GUIDE_BEST_PRACTICES.md) - Tips and patterns

---

## Quick Start

### Installation

```bash
pip install llm-scraper
```

### Basic Usage

```python
from llm_scraper import Article
from pydantic import HttpUrl
import requests

# Fetch HTML
url = "https://example.com/article"
html = requests.get(url).text

# Parse with default extraction
article = Article.from_html(html, HttpUrl(url))

print(f"Title: {article.title}")
print(f"Authors: {article.authors}")
print(f"Content length: {len(article.content)}")
```

### Using Domain-Specific Config

```python
from llm_scraper import Article
from llm_scraper.models.selector import ParserConfig
from pydantic import HttpUrl
import requests

# Load domain config
with open('configs/en/e/example.com.json') as f:
    config = ParserConfig.model_validate_json(f.read())

# Fetch and parse
html = requests.get('https://example.com/article').text
article = Article.from_html(html, HttpUrl('https://example.com/article'), parser_config=config)

# Access extracted data
print(f"Title: {article.title}")
print(f"Authors: {[a.name for a in article.authors]}")
print(f"Published: {article.metadata.published_at}")
print(f"Tags: {article.metadata.tags}")
print(f"Word count: {article.computed_word_count}")
```

---

## Core Features

### 🎯 Accurate Extraction
- Domain-specific parser configurations
- Fallback selector chains for robustness
- Parent scoping to avoid false matches
- Support for multiple selector formats

### 📊 Rich Metadata
- OpenGraph and Twitter Card extraction
- Schema.org JSON-LD parsing
- Author information
- Publication dates
- Tags and topics

### 🔧 Flexible Configuration
- JSON-based parser configs
- Multiple selector formats (string, array, config objects)
- Per-selector attribute extraction
- Parent element scoping

### 🚀 Production Ready
- Pydantic validation
- Comprehensive error handling
- Deterministic UUID generation
- Token estimation for LLMs

---

## Architecture

```
llm_scraper/
├── models/
│   ├── selector.py       # ParserConfig, ElementSelector, SelectorConfig
│   ├── meta.py           # Metadata extraction models
│   ├── schema.py         # Schema.org models
│   └── base.py           # Base models
├── parsers/
│   ├── base.py           # BaseParser, extraction logic
│   └── configs/          # Domain-specific configs
│       └── {lang}/{char}/{domain}.json
├── articles.py           # Article model
└── utils/                # Utilities
```

---

## Configuration Structure

### ParserConfig (JSON)
```json
{
  "domain": "example.com",
  "lang": "en",
  "type": "article",
  
  "title": {
    "css_selector": "h1.title",
    "type": "text"
  },
  
  "content": {
    "css_selector": "article",
    "type": "html"
  },
  
  "authors": {
    "css_selector": [
      {"selector": "a", "parent": ".byline"},
      ".author"
    ],
    "type": "text",
    "all": true
  },
  
  "cleanup": [".ads", ".popup"]
}
```

### Article Model (Output)
```python
Article(
    id="uuid-v5-from-url",
    title="Article Title",
    description="Summary...",
    content="Full text content...",
    authors=[ArticleAuthor(name="John Doe")],
    metadata=ArticleMetadata(
        language="en",
        tags=["tag1", "tag2"],
        topics=["topic1"],
        published_at=datetime(...),
        schema_org={...}  # Full Schema.org data
    ),
    provenance=Provenance(
        source_url="https://...",
        domain="example.com"
    )
)
```

---

## Key Concepts

### Selector Formats

**1. Simple String**
```json
"css_selector": "h1.title"
```

**2. Fallback Chain**
```json
"css_selector": ["h1.title", "h1.post-title", "h1"]
```

**3. Config Objects**
```json
"css_selector": [
    {"selector": "time", "attribute": "datetime"},
    {"selector": ".date"}
]
```

**4. Parent Scoping**
```json
"css_selector": [
    {"selector": "a", "attribute": "href", "parent": ".byline"}
]
```

### Extraction Pipeline

```
HTML Input
    ↓
1. Load ParserConfig (domain-specific)
    ↓
2. BaseParser.parse()
   - Apply cleanup rules
   - Try selectors (fallback chain)
   - Apply parent scoping
   - Extract text/html/attribute
    ↓
3. get_metadata()
   - Extract OpenGraph tags
   - Parse Schema.org JSON-LD
   - Extract language from HTML
    ↓
4. Article.from_html()
   - Merge parsed data + metadata
   - Generate UUID v5 from URL
   - Normalize content
   - Calculate word count & tokens
    ↓
Article Model Output
```

---

## Common Use Cases

### 1. News Article Extraction
```python
# Load news-specific config
config = ParserConfig.model_validate_json(open('configs/en/n/news-site.json').read())
article = Article.from_html(html, url, parser_config=config)

# Access structured data
print(f"Headline: {article.title}")
print(f"Authors: {', '.join(a.name for a in article.authors)}")
print(f"Published: {article.metadata.published_at}")
print(f"Tags: {article.metadata.tags}")
```

### 2. Blog Post Extraction
```python
# Generic blog extraction
article = Article.from_html(html, url)

# Chunk for RAG
chunks = article.chunk_by_token_estimate(max_tokens=800)
print(f"Created {len(chunks)} chunks")
```

### 3. Multi-Language Content
```python
# Load Vietnamese config
config = ParserConfig.model_validate_json(open('configs/vi/v/vnexpress.net.json').read())
article = Article.from_html(html, url, parser_config=config)
print(f"Language: {article.metadata.language}")  # "vi"
```

### 4. Schema.org Extraction
```python
article = Article.from_html(html, url, parser_config=config)

# Access raw Schema.org data
if article.metadata.schema_org:
    schema = article.metadata.schema_org
    print(f"Type: {schema.get('@type')}")
    print(f"Publisher: {schema.get('publisher', {}).get('name')}")
```

---

## Testing

### Validation Script
```bash
python scripts/validate_article_fixture.py fixtures/en/e/example.com.json
```

### Unit Tests
```bash
pytest tests/
```

### Browser Testing
```javascript
// Test selectors in browser console
document.querySelectorAll('.author-name')

// Test with parent
const parent = document.querySelector('.byline');
parent.querySelectorAll('a');
```

---

## Contributing

### Adding Domain Configs

1. Create config file: `configs/{lang}/{char}/{domain}.json`
2. Test with validation script
3. Add fixture: `fixtures/{lang}/{char}/{domain}.json`
4. Submit PR

See [GUIDE_DOMAIN_CONFIG.md](GUIDE_DOMAIN_CONFIG.md) for details.

---

## Resources

- **[Selector Guide](SELECTOR_GUIDE.md)** - Complete selector documentation
- [GitHub Repository](https://github.com/thewebscraping/llm-scraper)
- [Issue Tracker](https://github.com/thewebscraping/llm-scraper/issues)

---

## Support

- 📧 Email: support@example.com
- 💬 Discord: [Join our community](https://discord.gg/...)
- 🐛 Issues: [GitHub Issues](https://github.com/thewebscraping/llm-scraper/issues)

---

## License

MIT License - See [LICENSE](../LICENSE) for details.

## Environment Variables (Quick Reference)

Core Vector/RAG:
- OPENAI_API_KEY
- ASTRA_DB_APPLICATION_TOKEN
- ASTRA_DB_API_ENDPOINT
- ASTRA_DB_COLLECTION_NAME

Bulk Scraping & Tasks:
- REDIS_URL
- SYSTEM_SCRAPE_SECRET (protect sitemap/rss modes via X-System-Key header)
- SCRAPE_RESULT_TTL_DAYS (default 7)
- SCRAPE_RESULT_MAX_FULL (cap storing full list payload)
- MAX_CONCURRENT_SCRAPES (default 8)
- SCRAPE_TIMEOUT_SECONDS (default 20)

Hashing (cache URL keys):
- LLM_SCRAPER_HASH_ALGO (md5|sha1|sha256|hmac-sha256)
- LLM_SCRAPER_HASH_SECRET (required for hmac-sha256)
