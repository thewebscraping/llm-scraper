# Article Module Architecture Guide

**Version:** 1.0  
**Last Updated:** November 9, 2025

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Models](#core-models)
4. [Utility Functions](#utility-functions)
5. [Validators & Computed Fields](#validators--computed-fields)
6. [Factory Methods](#factory-methods)
7. [Chunking Strategies](#chunking-strategies)
8. [RAG Integration](#rag-integration)
9. [Usage Examples](#usage-examples)
10. [Best Practices](#best-practices)

---

## Overview

The `articles.py` module provides a comprehensive data model for web article extraction, storage, and RAG (Retrieval-Augmented Generation) pipeline integration. It's built on Pydantic for robust validation and includes advanced features like:

- **Automatic metadata extraction** from HTML
- **Flexible chunking strategies** for LLM context windows
- **Provenance tracking** for data lineage
- **Quality signals** for content assessment
- **Schema.org integration** for structured data
- **RAG-ready document conversion**

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Article Model                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Core Fields                                          │   │
│  │  - id, title, description, content                   │   │
│  │  - authors: List[ArticleAuthor]                      │   │
│  │  - provenance: Provenance                            │   │
│  │  - metadata: ArticleMetadata                         │   │
│  │  - license: LicenseInfo                              │   │
│  │  - chunks: List[ArticleChunk]                        │   │
│  │  - quality: QualitySignals                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Computed Fields (Auto-calculated)                    │   │
│  │  - computed_word_count                               │   │
│  │  - computed_token_estimate                           │   │
│  │  - computed_reading_time                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Methods                                              │   │
│  │  - from_html() [Factory]                             │   │
│  │  - chunk_by_char()                                   │   │
│  │  - chunk_by_token_estimate()                         │   │
│  │  - to_rag_documents()                                │   │
│  │  - summary()                                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Models

### 1. **ArticleAuthor**

Represents an article author with optional contact information.

```python
class ArticleAuthor(BaseModel):
    name: str                          # Required: Author display name
    email: Optional[str]               # Optional: Contact email
    profile_url: Optional[HttpUrl]     # Optional: Author profile/social link
    affiliation: Optional[str]         # Optional: Organization/affiliation
```

**Use Cases:**
- Multiple authors per article
- Author profile linking
- Attribution tracking

**Example:**
```python
author = ArticleAuthor(
    name="Jane Doe",
    email="jane@example.com",
    profile_url="https://example.com/authors/jane",
    affiliation="Tech News Network"
)
```

---

### 2. **CrawlerInfo**

Tracks how and when the article was fetched.

```python
class CrawlerInfo(BaseModel):
    crawler_name: Optional[str]        # e.g., "llm-scraper/0.1.1"
    user_agent: Optional[str]          # User-Agent string used
    ip: Optional[str]                  # IP address of fetcher
    fetch_duration_ms: Optional[int]   # Fetch time in milliseconds
    fetch_status: Optional[int]        # HTTP status code (200, 404, etc.)
    fetched_at: datetime               # Auto-set to UTC now
```

**Use Cases:**
- Debugging fetch issues
- Performance monitoring
- Compliance tracking (User-Agent disclosure)

---

### 3. **Provenance**

Complete data lineage for the article.

```python
class Provenance(BaseModel):
    source_url: HttpUrl                      # Required: Canonical URL
    domain: Optional[str]                    # e.g., "example.com"
    original_html_saved: bool = False        # HTML snapshot flag
    snapshot_path: Optional[str]             # Path to saved HTML
    tls_ja3: Optional[str]                   # TLS fingerprint
    crawler: Optional[CrawlerInfo]           # Fetch metadata
```

**Key Features:**
- **Deterministic IDs**: URL → UUID v5 mapping
- **Snapshot support**: Save original HTML for audits
- **Security tracking**: TLS/JA3 fingerprints

**Example:**
```python
provenance = Provenance(
    source_url="https://example.com/article/123",
    domain="example.com",
    original_html_saved=True,
    snapshot_path="s3://bucket/snapshots/article-123.html",
    crawler=CrawlerInfo(
        crawler_name="llm-scraper/1.0",
        fetch_status=200,
        fetch_duration_ms=1234
    )
)
```

---

### 4. **ArticleMetadata**

Rich metadata extracted from article and meta tags.

```python
class ArticleMetadata(BaseModel):
    language: Optional[str]                  # ISO-639-1 code (e.g., "en")
    tags: List[str]                          # Article tags/keywords
    topics: List[str]                        # Categorization topics
    canonical_url: Optional[HttpUrl]         # Canonical URL
    word_count: Optional[int]                # Total word count
    reading_time_minutes: Optional[float]    # Estimated reading time
    published_at: Optional[datetime]         # Publish date
    modified_at: Optional[datetime]          # Last modified date
    inferred_source: Optional[str]           # Publisher name
    schema_org: Optional[Dict[str, Any]]     # Raw Schema.org JSON-LD
```

**Schema.org Integration:**
The `schema_org` field stores complete JSON-LD data from `<script type="application/ld+json">` tags, preserving all structured data for downstream processing.

**Example:**
```python
metadata = ArticleMetadata(
    language="en",
    tags=["AI", "Machine Learning", "GPT-4"],
    topics=["Technology", "Artificial Intelligence"],
    word_count=1500,
    reading_time_minutes=6.8,
    published_at=datetime(2024, 11, 1, 10, 0, 0, tzinfo=timezone.utc),
    schema_org={
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Breaking News in AI",
        "datePublished": "2024-11-01T10:00:00Z"
    }
)
```

---

### 5. **ArticleChunk**

Represents a single chunk of article content for RAG systems.

```python
class ArticleChunk(BaseModel):
    index: int                           # Sequential chunk index (0-based)
    content: str                         # Chunk text (cleaned)
    char_length: int                     # Length in characters
    word_count: int                      # Word count
    token_estimate: int                  # Estimated token count
    embedding: Optional[List[float]]     # Vector embedding (if computed)
    metadata: Dict[str, Any]             # Per-chunk metadata
```

**Factory Method:**
```python
@classmethod
def from_text(cls, index: int, text: str) -> "ArticleChunk":
    """Auto-calculate all metrics from raw text."""
```

**Example:**
```python
chunk = ArticleChunk.from_text(
    index=0,
    text="This is the first chunk of the article..."
)
# Auto-sets: char_length, word_count, token_estimate
```

---

### 6. **QualitySignals**

Quality assessment metrics for content.

```python
class QualitySignals(BaseModel):
    extraction_confidence: Optional[float]   # 0.0-1.0: Extraction quality
    duplicate_score: Optional[float]         # 0.0-1.0: Duplication likelihood
    content_quality: Optional[float]         # 0.0-1.0: Overall quality
    notes: Optional[str]                     # Human-readable notes
```

**Use Cases:**
- Filtering low-quality content
- Prioritizing high-confidence extractions
- Debugging extraction issues

---

### 7. **Article** (Main Model)

The complete article representation.

```python
class Article(BaseModel):
    # Core Content
    id: Optional[str]                        # Auto-generated UUID v5 from URL
    title: Optional[str]                     # Article title
    description: Optional[str]               # Meta description
    content: str                             # Cleaned text (HTML stripped)
    
    # Structured Data
    authors: List[ArticleAuthor]             # Author information
    provenance: Provenance                   # Data lineage
    metadata: ArticleMetadata                # Rich metadata
    license: LicenseInfo                     # License/copyright info
    
    # Optional Data
    raw_html: Optional[str]                  # Original HTML
    extraction: Optional[ExtractionTrace]    # Extraction debug info
    chunks: List[ArticleChunk]               # Content chunks for RAG
    embedding: Optional[List[float]]         # Document-level embedding
    vector_id: Optional[str]                 # Vector DB identifier
    quality: QualitySignals                  # Quality metrics
    extras: Dict[str, Any]                   # Custom fields
    
    # Timestamps
    created_at: datetime                     # Auto-set to UTC now
    updated_at: datetime                     # Auto-set to UTC now
```

---

## Utility Functions

All utility functions have been refactored to `utils/` for better code organization:

### From `utils/text.py`:

```python
WORD_RE = re.compile(r"\w+", re.UNICODE)     # Unicode word regex

def estimate_tokens_from_text(text: str, avg_token_per_word: float = 1.33) -> int:
    """Fast heuristic token estimation (1.33 tokens/word for GPT models)."""

def count_words(text: str) -> int:
    """Count words using unicode-aware regex."""

def sha256_hex(value: str) -> str:
    """Generate SHA-256 hash (for content deduplication)."""
```

### From `utils/datetime.py`:

```python
def now_utc() -> datetime:
    """Get current UTC datetime with timezone awareness."""
```

---

## Validators & Computed Fields

### Field Validators

#### 1. **Content Normalization** (`_normalize_content`)

```python
@field_validator("content", mode="before")
@classmethod
def _normalize_content(cls, v: str) -> str:
    """
    Normalize whitespace, remove control chars, trim.
    - Replaces \\r\\n\\t with spaces
    - Removes non-breaking spaces (\\u00A0)
    - Collapses multiple spaces
    - Strips leading/trailing whitespace
    """
```

**Input:**
```python
"Hello\\n\\nWorld  \\t  Multiple   Spaces\\u00A0Here"
```

**Output:**
```python
"Hello World Multiple Spaces Here"
```

---

### Computed Fields

Computed fields are **automatically calculated** and cached. They don't require database storage but are included in serialization.

#### 1. **`computed_word_count`**

```python
@computed_field
def computed_word_count(self) -> int:
    """
    Priority:
    1. Use metadata.word_count if available
    2. Otherwise, count words in content using WORD_RE
    """
```

#### 2. **`computed_token_estimate`**

```python
@computed_field
def computed_token_estimate(self) -> int:
    """Estimate tokens using 1.33 tokens/word heuristic."""
```

#### 3. **`computed_reading_time`**

```python
@computed_field
def computed_reading_time(self) -> float:
    """
    Estimate reading time in minutes.
    Formula: word_count / 220 words per minute (average reading speed)
    """
```

**Example:**
```python
article = Article(content="..." * 1000)  # ~1000 words
print(article.computed_word_count)       # 1000
print(article.computed_token_estimate)   # 1330
print(article.computed_reading_time)     # 4.55 (minutes)
```

---

### Model Validators

#### **Auto-Generate ID** (`_generate_id_if_missing`)

```python
@model_validator(mode='after')
def _generate_id_if_missing(self):
    """
    Generate deterministic UUID v5 from source URL if ID not provided.
    Uses uuid.NAMESPACE_URL for consistency.
    """
```

**Example:**
```python
article = Article(
    content="...",
    provenance=Provenance(source_url="https://example.com/article/123")
)
# Auto-generates: id = "a1b2c3d4-..."  (same URL = same UUID)
```

---

## Factory Methods

### `Article.from_html()`

The primary factory method for creating articles from raw HTML.

```python
@classmethod
def from_html(
    cls, 
    html: str, 
    url: HttpUrl, 
    parser_config: Optional[ParserConfig] = None, 
    **kwargs
) -> "Article":
    """
    Factory method to create an Article from raw HTML.
    
    Process Flow:
    1. Extract metadata using get_metadata(html)
       - OpenGraph tags
       - Twitter Card tags
       - Schema.org JSON-LD
       - Standard meta tags
    
    2. Extract content using get_parsed_data(html, parser_config)
       - If parser_config provided: use domain-specific selectors
       - Otherwise: fallback to <main>, <article>, or <body>
    
    3. Merge metadata from both sources
       - Priority: parser_config > meta tags
       - Combine authors, tags, topics
    
    4. Create Article instance with validation
    
    5. Call ensure_metadata_counts() to populate computed fields
    
    Args:
        html: Raw HTML content
        url: Article URL (used for provenance and ID generation)
        parser_config: Optional domain-specific parser configuration
        **kwargs: Additional fields to pass to Article constructor
    
    Returns:
        Validated Article instance
    
    Raises:
        ArticleCreationError: If HTML is empty or content extraction fails
    """
```

**Example 1: With ParserConfig**

```python
from llm_scraper.models.selector import ParserConfig, ElementSelector

config = ParserConfig(
    domain="example.com",
    content=ElementSelector(css_selector="article.main-content"),
    title=ElementSelector(css_selector="h1.article-title"),
    authors=ElementSelector(css_selector="span.author-name", all=True),
    date_published=ElementSelector(css_selector="time[datetime]", attribute="datetime"),
    tags=ElementSelector(css_selector="a.tag", all=True)
)

article = Article.from_html(
    html=html_content,
    url="https://example.com/article/123",
    parser_config=config
)
```

**Example 2: Fallback Mode (No Config)**

```python
article = Article.from_html(
    html=html_content,
    url="https://example.com/article/123"
)
# Uses: get_metadata() for meta tags + <main>/<article>/<body> extraction
```

---

## Chunking Strategies

The Article model provides two chunking strategies for RAG systems:

### 1. **Character-Based Chunking** (`chunk_by_char`)

```python
def chunk_by_char(
    self,
    max_chars: int = 2000,
    overlap_chars: int = 200,
    preserve_headline: bool = True,
) -> List[ArticleChunk]:
    """
    Chunk article content into fixed-size character windows.
    
    Algorithm:
    1. Optionally remove title from content start
    2. Create chunks of max_chars length
    3. Apply overlap_chars between chunks
    4. Create ArticleChunk instances with metadata
    
    Args:
        max_chars: Maximum characters per chunk
        overlap_chars: Characters to overlap between chunks
        preserve_headline: Remove title from content if it appears at start
    
    Returns:
        List of ArticleChunk objects (also sets self.chunks)
    """
```

**Use Cases:**
- Simple, predictable chunk sizes
- When character count matters more than semantic boundaries

**Example:**
```python
article = Article.from_html(html, url)
chunks = article.chunk_by_char(
    max_chars=1500,
    overlap_chars=150,
    preserve_headline=True
)
print(f"Created {len(chunks)} chunks")
for chunk in chunks[:3]:
    print(f"Chunk {chunk.index}: {chunk.char_length} chars, ~{chunk.token_estimate} tokens")
```

---

### 2. **Token-Based Chunking** (`chunk_by_token_estimate`)

**Recommended for LLM context windows** - more accurate than character-based.

```python
def chunk_by_token_estimate(
    self,
    max_tokens: int = 800,
    overlap_tokens: int = 64,
    sentence_split: bool = True,
) -> List[ArticleChunk]:
    """
    Chunk by estimated token count using sentence/word boundaries.
    
    Algorithm:
    1. Split by sentences (regex) or words
    2. Build chunks until max_tokens reached
    3. Apply overlap_tokens between chunks
    4. Handle edge cases (oversized sentences)
    
    Args:
        max_tokens: Maximum estimated tokens per chunk
        overlap_tokens: Tokens to overlap between chunks
        sentence_split: Use sentence boundaries (True) or word boundaries (False)
    
    Returns:
        List of ArticleChunk objects (also sets self.chunks)
    """
```

**Sentence Split Regex:**
```python
r"(?<=[.?!])\s+(?=[A-Z0-9\"'"'])"
# Matches: period/question/exclamation + space + capital letter
```

**Use Cases:**
- LLM context windows (stay under token limits)
- Semantic chunking (sentence boundaries)
- RAG retrieval (more coherent chunks)

**Example:**
```python
article = Article.from_html(html, url)
chunks = article.chunk_by_token_estimate(
    max_tokens=512,      # GPT-4 safe chunk size
    overlap_tokens=50,   # Overlap for context continuity
    sentence_split=True  # Preserve sentence boundaries
)

# Add embeddings to chunks
for chunk in chunks:
    chunk.embedding = get_embedding(chunk.content)  # Your embedding function

# Ready for vector DB insertion
docs = article.to_rag_documents()
```

---

## RAG Integration

### **`to_rag_documents()`**

Converts chunks to RAG-ready documents for vector databases.

```python
def to_rag_documents(self) -> List[Dict[str, Any]]:
    """
    Convert chunks to documents for vector DB insertion.
    
    Output Format:
    [
        {
            "id": "article-uuid-chunk-0",
            "text": "chunk content...",
            "meta": {
                "article_id": "article-uuid",
                "title": "Article Title",
                "source_url": "https://...",
                "index": 0,
                "domain": "example.com"
            }
        },
        ...
    ]
    """
```

**Integration Examples:**

#### Pinecone:
```python
import pinecone

article = Article.from_html(html, url)
article.chunk_by_token_estimate(max_tokens=512)

# Generate embeddings
for chunk in article.chunks:
    chunk.embedding = model.encode(chunk.content)

# Prepare for Pinecone
vectors = []
for chunk in article.chunks:
    vectors.append({
        "id": f"{article.id}-chunk-{chunk.index}",
        "values": chunk.embedding,
        "metadata": {
            "text": chunk.content,
            "title": article.title,
            "url": str(article.provenance.source_url),
            "chunk_index": chunk.index
        }
    })

index.upsert(vectors=vectors)
```

#### Weaviate:
```python
import weaviate

docs = article.to_rag_documents()
for doc in docs:
    client.data_object.create(
        data_object={
            "text": doc["text"],
            "article_id": doc["meta"]["article_id"],
            "title": doc["meta"]["title"],
            "source_url": doc["meta"]["source_url"]
        },
        class_name="ArticleChunk"
    )
```

---

## Usage Examples

### Example 1: Basic Article Creation

```python
from llm_scraper.articles import Article
from pydantic import HttpUrl

# Create article manually
article = Article(
    title="Understanding LLMs",
    content="Large Language Models are transforming AI...",
    provenance=Provenance(
        source_url=HttpUrl("https://example.com/article/1")
    )
)

# Auto-generated fields
print(article.id)                      # UUID v5 from URL
print(article.computed_word_count)     # 6
print(article.computed_token_estimate) # 8
print(article.computed_reading_time)   # 0.03 minutes
```

---

### Example 2: From HTML with Config

```python
import tls_requests
from llm_scraper.articles import Article
from llm_scraper.models.selector import ParserConfig

# Fetch HTML
response = tls_requests.get("https://example.com/article/123")
html = response.text

# Load domain config
config = ParserConfig.from_json_file("configs/en/e/example.com.json")

# Create article
article = Article.from_html(
    html=html,
    url=response.url,
    parser_config=config
)

# Access structured data
print(f"Title: {article.title}")
print(f"Authors: {[a.name for a in article.authors]}")
print(f"Published: {article.metadata.published_at}")
print(f"Tags: {article.metadata.tags}")
print(f"Schema.org: {article.metadata.schema_org}")
```

---

### Example 3: RAG Pipeline

```python
from llm_scraper.articles import Article
from sentence_transformers import SentenceTransformer

# Load embedding model
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Create article
article = Article.from_html(html, url)

# Chunk for RAG (512 tokens max, 50 token overlap)
chunks = article.chunk_by_token_estimate(
    max_tokens=512,
    overlap_tokens=50,
    sentence_split=True
)

# Generate embeddings
for chunk in chunks:
    chunk.embedding = embedder.encode(chunk.content).tolist()

# Convert to RAG documents
rag_docs = article.to_rag_documents()

# Insert into vector DB (pseudo-code)
vector_db.insert(rag_docs)

# Query later
query_embedding = embedder.encode("What are LLMs?")
results = vector_db.search(query_embedding, top_k=5)
```

---

### Example 4: Quality Filtering

```python
articles = []
for url in urls:
    html = fetch(url)
    article = Article.from_html(html, url)
    
    # Set quality signals
    article.quality.extraction_confidence = calculate_confidence(article)
    article.quality.content_quality = assess_quality(article.content)
    
    # Filter low-quality
    if article.quality.extraction_confidence > 0.7:
        if article.computed_word_count >= 300:
            articles.append(article)

print(f"Kept {len(articles)} high-quality articles")
```

---

### Example 5: Batch Processing

```python
from concurrent.futures import ThreadPoolExecutor
import tls_requests

def process_url(url: str) -> Article:
    """Fetch and parse article from URL."""
    try:
        response = tls_requests.get(url, timeout=10)
        response.raise_for_status()
        
        article = Article.from_html(
            html=response.text,
            url=response.url
        )
        article.chunk_by_token_estimate(max_tokens=512)
        return article
    except Exception as e:
        print(f"Error processing {url}: {e}")
        return None

# Process 100 URLs in parallel
urls = [...]  # Your URL list
with ThreadPoolExecutor(max_workers=10) as executor:
    articles = list(executor.map(process_url, urls))

# Filter successful
articles = [a for a in articles if a is not None]
print(f"Processed {len(articles)} articles")
```

---

## Best Practices

### 1. **Always Use `from_html()` Factory**

✅ **Good:**
```python
article = Article.from_html(html, url, parser_config=config)
```

❌ **Bad:**
```python
article = Article(content=extract_content(html), ...)  # Manual extraction
```

**Why:** `from_html()` handles metadata extraction, validation, and error handling.

---

### 2. **Choose Appropriate Chunking Strategy**

| Use Case | Strategy | Settings |
|----------|----------|----------|
| General RAG | `chunk_by_token_estimate` | `max_tokens=512, overlap_tokens=50` |
| Long context models | `chunk_by_token_estimate` | `max_tokens=2000, overlap_tokens=100` |
| Precise char limits | `chunk_by_char` | `max_chars=1500, overlap_chars=150` |
| Semantic coherence | `chunk_by_token_estimate` | `sentence_split=True` |

---

### 3. **Validate Extraction Quality**

```python
article = Article.from_html(html, url)

# Check content quality
if len(article.content) < 200:
    print("Warning: Suspiciously short content")

if article.computed_word_count < 100:
    print("Warning: Very short article")

if not article.title:
    print("Warning: No title extracted")

if not article.authors:
    print("Warning: No authors found")
```

---

### 4. **Preserve Raw HTML for Auditing**

```python
article = Article.from_html(
    html=html,
    url=url,
    raw_html=html  # Save original HTML
)

article.provenance.original_html_saved = True
article.provenance.snapshot_path = f"s3://bucket/{article.id}.html"
```

---

### 5. **Use Computed Fields, Don't Store Redundantly**

✅ **Good:**
```python
article = Article.from_html(html, url)
# Use computed fields directly
reading_time = article.computed_reading_time
```

❌ **Bad:**
```python
article.metadata.reading_time_minutes = calculate_reading_time(article.content)
# Redundant - already computed automatically
```

---

### 6. **Handle Errors Gracefully**

```python
from llm_scraper.exceptions import ArticleCreationError

try:
    article = Article.from_html(html, url, parser_config=config)
except ArticleCreationError as e:
    print(f"Failed to create article: {e}")
    # Fallback to simpler extraction or skip
```

---

### 7. **Batch Insert RAG Documents**

```python
# Collect all documents first
all_docs = []
for article in articles:
    article.chunk_by_token_estimate()
    all_docs.extend(article.to_rag_documents())

# Batch insert (more efficient)
vector_db.insert_batch(all_docs, batch_size=100)
```

---

## Summary

The `articles.py` module provides:

- ✅ **Robust data models** with Pydantic validation
- ✅ **Automatic metadata extraction** from HTML
- ✅ **Flexible chunking** for RAG systems
- ✅ **Provenance tracking** for data lineage
- ✅ **Quality signals** for content filtering
- ✅ **Schema.org integration** for structured data
- ✅ **RAG-ready output** for vector databases

**Key Takeaways:**

1. Use `Article.from_html()` for HTML → Article conversion
2. Choose chunking strategy based on LLM context window
3. Leverage computed fields for automatic calculations
4. Track provenance for compliance and debugging
5. Filter by quality signals before RAG ingestion

---

**Questions or Issues?**  
Check the [main documentation](README.md) or open an issue on GitHub.
