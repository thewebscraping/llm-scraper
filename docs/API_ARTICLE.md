# Article Model API Reference

Complete reference for the `Article` model and related classes.

## Table of Contents

1. [Article](#article)
2. [ArticleMetadata](#articlemetadata)
3. [ArticleAuthor](#articleauthor)
4. [Provenance](#provenance)
5. [ArticleChunk](#articlechunk)
6. [Factory Methods](#factory-methods)
7. [Computed Fields](#computed-fields)
8. [Instance Methods](#instance-methods)

---

## Article

The main model representing a parsed article with full metadata.

### Fields

```python
class Article(BaseModel):
    id: Optional[str] = None                      # UUID v5 (auto-generated from URL)
    title: Optional[str] = None                   # Article title
    description: Optional[str] = None             # Summary/excerpt
    content: str                                  # Cleaned text content (HTML stripped)
    authors: List[ArticleAuthor] = []            # List of authors
    provenance: Provenance                        # Source information
    metadata: ArticleMetadata                     # Rich metadata
    license: LicenseInfo                          # License information
    raw_html: Optional[str] = None               # Original HTML (optional)
    extraction: Optional[ExtractionTrace] = None  # Extraction metadata
    chunks: List[ArticleChunk] = []              # Content chunks for RAG
    embedding: Optional[List[float]] = []        # Document embedding
    vector_id: Optional[str] = None              # Vector DB ID
    quality: QualitySignals                       # Quality metrics
    extras: Dict[str, Any] = {}                  # Additional data
    created_at: datetime                          # Creation timestamp
    updated_at: datetime                          # Last update timestamp
```

### Example

```python
from llm_scraper import Article
from pydantic import HttpUrl

article = Article.from_html(
    html="<article>...</article>",
    url=HttpUrl("https://example.com/article"),
    parser_config=config
)

print(article.model_dump_json(indent=2))
```

**Output:**
```json
{
  "id": "23d6c940-19f6-5af2-98f2-b6d9d1d92303",
  "title": "Article Title",
  "description": "Brief summary...",
  "content": "Full article text content...",
  "authors": [
    {
      "name": "John Doe",
      "email": null,
      "profile_url": null,
      "affiliation": null
    }
  ],
  "provenance": {
    "source_url": "https://example.com/article",
    "domain": "example.com",
    "original_html_saved": false,
    "snapshot_path": null,
    "tls_ja3": null,
    "crawler": null
  },
  "metadata": {
    "language": "en",
    "tags": ["tag1", "tag2"],
    "topics": ["topic1"],
    "canonical_url": null,
    "word_count": 500,
    "reading_time_minutes": 2.27,
    "published_at": "2025-11-08T18:53:57+00:00",
    "modified_at": null,
    "inferred_source": null,
    "schema_org": {...}
  },
  "created_at": "2025-11-09T03:30:00+00:00",
  "updated_at": "2025-11-09T03:30:00+00:00"
}
```

---

## ArticleMetadata

Rich metadata extracted from the article.

### Fields

```python
class ArticleMetadata(BaseModel):
    language: Optional[str] = None                    # ISO-639-1 code (e.g., "en", "vi")
    tags: Optional[List[str]] = []                   # Article tags
    topics: Optional[List[str]] = []                 # Topics/categories
    canonical_url: Optional[HttpUrl] = None          # Canonical URL
    word_count: Optional[int] = None                 # Word count
    reading_time_minutes: Optional[float] = None     # Estimated reading time
    published_at: Optional[datetime] = None          # Publication date
    modified_at: Optional[datetime] = None           # Last modified date
    inferred_source: Optional[str] = None            # Publisher name
    schema_org: Optional[Dict[str, Any]] = None     # Raw Schema.org JSON-LD
```

### Example

```python
metadata = article.metadata

print(f"Language: {metadata.language}")
print(f"Published: {metadata.published_at}")
print(f"Tags: {metadata.tags}")
print(f"Word count: {metadata.word_count}")
print(f"Reading time: {metadata.reading_time_minutes} min")

# Access Schema.org data
if metadata.schema_org:
    schema_type = metadata.schema_org.get('@type')
    publisher = metadata.schema_org.get('publisher', {}).get('name')
    print(f"Schema type: {schema_type}")
    print(f"Publisher: {publisher}")
```

---

## ArticleAuthor

Author information.

### Fields

```python
class ArticleAuthor(BaseModel):
    name: str                              # Author name (required)
    email: Optional[str] = None           # Contact email
    profile_url: Optional[HttpUrl] = None # Author profile/social link
    affiliation: Optional[str] = None     # Organization/affiliation
```

### Example

```python
for author in article.authors:
    print(f"Author: {author.name}")
    if author.profile_url:
        print(f"  Profile: {author.profile_url}")
    if author.affiliation:
        print(f"  Affiliation: {author.affiliation}")
```

---

## Provenance

Source and crawling information.

### Fields

```python
class Provenance(BaseModel):
    source_url: HttpUrl                           # Article URL (required)
    domain: Optional[str] = None                 # Domain (e.g., "example.com")
    original_html_saved: Optional[bool] = False  # Whether HTML was saved
    snapshot_path: Optional[str] = None          # Path to saved HTML
    tls_ja3: Optional[str] = None               # TLS fingerprint
    crawler: Optional[CrawlerInfo] = None        # Crawler metadata
```

### Example

```python
prov = article.provenance
print(f"Source: {prov.source_url}")
print(f"Domain: {prov.domain}")

if prov.crawler:
    print(f"Crawler: {prov.crawler.crawler_name}")
    print(f"Fetched at: {prov.crawler.fetched_at}")
    print(f"Status: {prov.crawler.fetch_status}")
```

---

## ArticleChunk

Content chunk for RAG/vector search.

### Fields

```python
class ArticleChunk(BaseModel):
    index: int = 1                          # Chunk index (0-based)
    content: str = ""                       # Chunk text
    char_length: int = 0                    # Character count
    word_count: int = 0                     # Word count
    token_estimate: int = 0                 # Estimated tokens
    embedding: Optional[List[float]] = None # Chunk embedding
    metadata: Dict[str, Any] = {}          # Per-chunk metadata
```

### Example

```python
# Create chunks
chunks = article.chunk_by_token_estimate(max_tokens=800, overlap_tokens=64)

for chunk in chunks:
    print(f"Chunk {chunk.index}:")
    print(f"  Tokens: {chunk.token_estimate}")
    print(f"  Words: {chunk.word_count}")
    print(f"  Preview: {chunk.content[:100]}...")
```

---

## Factory Methods

### Article.from_html()

Create an Article from raw HTML.

```python
@classmethod
def from_html(
    cls, 
    html: str, 
    url: HttpUrl, 
    parser_config: Optional[ParserConfig] = None, 
    **kwargs
) -> "Article"
```

**Parameters:**
- `html` (str): Raw HTML content
- `url` (HttpUrl): Article URL
- `parser_config` (ParserConfig, optional): Domain-specific parser config
- `**kwargs`: Additional Article fields to override

**Returns:**
- `Article`: Parsed article instance

**Raises:**
- `ArticleCreationError`: If HTML is empty or extraction fails

**Example:**

```python
from llm_scraper import Article
from llm_scraper.models.selector import ParserConfig
from pydantic import HttpUrl
import requests

# Without config (uses default extraction)
html = requests.get('https://example.com/article').text
article = Article.from_html(html, HttpUrl('https://example.com/article'))

# With domain config
with open('configs/en/e/example.com.json') as f:
    config = ParserConfig.model_validate_json(f.read())

article = Article.from_html(
    html=html,
    url=HttpUrl('https://example.com/article'),
    parser_config=config
)

# With overrides
article = Article.from_html(
    html=html,
    url=HttpUrl('https://example.com/article'),
    parser_config=config,
    extraction=ExtractionTrace(
        extractor="custom_v1",
        version="1.0.0",
        confidence=0.95
    )
)
```

---

## Computed Fields

These fields are automatically calculated from the article content.

### computed_word_count

```python
@computed_field
def computed_word_count(self) -> int
```

Returns word count from content. Uses `metadata.word_count` if available, otherwise counts words.

**Example:**
```python
print(f"Word count: {article.computed_word_count}")
```

### computed_token_estimate

```python
@computed_field
def computed_token_estimate(self) -> int
```

Estimates token count using heuristic (1.33 tokens per word).

**Example:**
```python
print(f"Estimated tokens: {article.computed_token_estimate}")
```

### computed_reading_time

```python
@computed_field
def computed_reading_time(self) -> float
```

Estimates reading time in minutes (220 words per minute).

**Example:**
```python
print(f"Reading time: {article.computed_reading_time} minutes")
```

---

## Instance Methods

### ensure_metadata_counts()

```python
def ensure_metadata_counts(self) -> None
```

Ensures `metadata.word_count` and `reading_time_minutes` are populated.

**Example:**
```python
article.ensure_metadata_counts()
assert article.metadata.word_count is not None
assert article.metadata.reading_time_minutes is not None
```

### chunk_by_char()

```python
def chunk_by_char(
    self,
    max_chars: int = 2000,
    overlap_chars: int = 200,
    preserve_headline: bool = True,
) -> List[ArticleChunk]
```

Chunks content by character count with optional overlap.

**Parameters:**
- `max_chars` (int): Maximum characters per chunk (default: 2000)
- `overlap_chars` (int): Overlap between chunks (default: 200)
- `preserve_headline` (bool): Remove title from first chunk (default: True)

**Returns:**
- `List[ArticleChunk]`: List of chunks

**Example:**
```python
chunks = article.chunk_by_char(
    max_chars=1500,
    overlap_chars=150,
    preserve_headline=True
)

print(f"Created {len(chunks)} chunks")
for chunk in chunks:
    print(f"Chunk {chunk.index}: {chunk.char_length} chars")
```

### chunk_by_token_estimate()

```python
def chunk_by_token_estimate(
    self,
    max_tokens: int = 800,
    overlap_tokens: int = 64,
    sentence_split: bool = True,
) -> List[ArticleChunk]
```

Chunks content by estimated token count. Safer for LLM context windows.

**Parameters:**
- `max_tokens` (int): Maximum tokens per chunk (default: 800)
- `overlap_tokens` (int): Overlap in tokens (default: 64)
- `sentence_split` (bool): Split on sentence boundaries (default: True)

**Returns:**
- `List[ArticleChunk]`: List of chunks

**Example:**
```python
chunks = article.chunk_by_token_estimate(
    max_tokens=800,
    overlap_tokens=64,
    sentence_split=True
)

for chunk in chunks:
    print(f"Chunk {chunk.index}:")
    print(f"  Tokens: {chunk.token_estimate}")
    print(f"  Words: {chunk.word_count}")
```

### to_rag_documents()

```python
def to_rag_documents(self) -> List[Dict[str, Any]]
```

Converts chunks to documents ready for vector DB / RAG system.

**Returns:**
- `List[Dict]`: List of document dicts

**Example:**
```python
# Chunk first
article.chunk_by_token_estimate(max_tokens=800)

# Convert to RAG documents
docs = article.to_rag_documents()

for doc in docs:
    print(f"ID: {doc['id']}")
    print(f"Text: {doc['text'][:100]}...")
    print(f"Meta: {doc['meta']}")

# Output format:
# {
#     "id": "uuid-chunk-0",
#     "text": "Chunk content...",
#     "meta": {
#         "article_id": "uuid",
#         "title": "Article Title",
#         "source_url": "https://...",
#         "index": 0,
#         "domain": "example.com"
#     }
# }
```

### touch_updated()

```python
def touch_updated(self) -> None
```

Updates `updated_at` timestamp to current UTC time.

**Example:**
```python
article.touch_updated()
print(f"Updated at: {article.updated_at}")
```

### summary()

```python
def summary(self) -> Dict[str, Any]
```

Returns compact summary for logs or listing APIs.

**Returns:**
- `Dict`: Summary dict

**Example:**
```python
summary = article.summary()
print(summary)

# Output:
# {
#     "id": "uuid",
#     "title": "Article Title",
#     "domain": "example.com",
#     "url": "https://...",
#     "word_count": 500,
#     "tokens_est": 665,
#     "chunks": 3,
#     "created_at": "2025-11-09T03:30:00+00:00"
# }
```

---

## Complete Example

```python
from llm_scraper import Article
from llm_scraper.models.selector import ParserConfig
from pydantic import HttpUrl
import requests

# Load config
with open('configs/en/c/cointelegraph.com.json') as f:
    config = ParserConfig.model_validate_json(f.read())

# Fetch HTML
url = 'https://cointelegraph.com/news/...'
html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text

# Parse article
article = Article.from_html(html, HttpUrl(url), parser_config=config)

# Access data
print(f"📄 {article.title}")
print(f"👤 By: {', '.join(a.name for a in article.authors)}")
print(f"📅 Published: {article.metadata.published_at}")
print(f"🏷️ Tags: {', '.join(article.metadata.tags[:5])}")
print(f"📊 {article.computed_word_count} words ({article.computed_reading_time} min read)")

# Chunk for RAG
chunks = article.chunk_by_token_estimate(max_tokens=800)
print(f"✂️ Created {len(chunks)} chunks")

# Convert to RAG docs
docs = article.to_rag_documents()
print(f"📚 {len(docs)} documents ready for vector DB")

# Save
with open('article.json', 'w') as f:
    f.write(article.model_dump_json(indent=2))
```

---

## See Also

- [Selector Guide](SELECTOR_GUIDE.md) - Parser configuration reference
- [Metadata API](API_METADATA.md) - Metadata extraction reference
- [Testing Guide](GUIDE_TESTING.md) - How to test extractions
