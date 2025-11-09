from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)

from .exceptions import ArticleCreationError
from .models.selector import ParserConfig
from .parsers.base import get_metadata, get_parsed_data
from .utils import WORD_RE, estimate_tokens_from_text, now_utc


class ArticleAuthor(BaseModel):
    name: str = Field(description="Author name (display)")
    email: Optional[str] = Field(default=None, description="Contact email if available")
    profile_url: Optional[HttpUrl] = Field(default=None, description="Author profile page or social link")
    affiliation: Optional[str] = Field(default=None, description="Affiliation or organization")
    model_config = {"frozen": False}


class CrawlerInfo(BaseModel):
    crawler_name: Optional[str] = Field(default=None, description="E.g., 'llm-scraper/0.1.1' or custom worker id")
    user_agent: Optional[str] = Field(default=None, description="User-Agent string used to fetch")
    ip: Optional[str] = Field(default=None, description="IP address that fetched (if known)")
    fetch_duration_ms: Optional[int] = Field(default=None, description="Milliseconds spent fetching")
    fetch_status: Optional[int] = Field(default=None, description="HTTP status code returned")
    fetched_at: datetime = Field(default_factory=now_utc, description="When fetch occurred")


class Provenance(BaseModel):
    source_url: HttpUrl = Field(description="Article canonical URL")
    domain: Optional[str] = Field(default=None, description="Root domain (e.g., example.com)")
    original_html_saved: Optional[bool] = Field(default=False, description="Whether raw HTML snapshot was saved")
    snapshot_path: Optional[str] = Field(default=None, description="Local/remote path to saved HTML snapshot")
    tls_ja3: Optional[str] = Field(default=None, description="TLS/JA3 fingerprint, if collected")
    crawler: Optional[CrawlerInfo] = Field(default=None)


class LicenseInfo(BaseModel):
    license: Optional[str] = Field(default=None, description="License or terms of use for scraped content")
    restricted: bool = Field(
        default=False,
        description="Whether the content is labeled restricted / paywalled",
    )
    copyright_holder: Optional[str] = Field(default=None, description="Copyright holder name if known")


class ExtractionTrace(BaseModel):
    extractor: str = Field(description="Name of extractor used (e.g., 'default_bs4', 'readability')")
    version: Optional[str] = Field(default=None, description="Extractor version")
    steps: List[str] = Field(default_factory=list, description="Short trace of steps performed")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence score 0..1")


class ArticleChunk(BaseModel):
    index: int = Field(default=1, ge=0)
    content: str = Field(default="", description="Chunk text (cleaned)")
    char_length: int = Field(default=0, description="Length in characters")
    word_count: int = Field(default=0, description="Word count of the chunk")
    token_estimate: int = Field(default=0, description="Estimated token count")
    embedding: Optional[List[float]] = Field(default=None, description="Embedding vector (if computed)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Per-chunk metadata (e.g., headings)")

    @classmethod
    def from_text(cls, index: int, text: str) -> "ArticleChunk":
        wc = len(WORD_RE.findall(text))
        return cls(
            index=index,
            content=text,
            char_length=len(text),
            word_count=wc,
            token_estimate=estimate_tokens_from_text(text),
        )


class ArticleMetadata(BaseModel):
    language: Optional[str] = Field(default=None, description="ISO-639-1 (or BCP-47) language code")
    tags: Optional[List[str]] = Field(default_factory=list)
    topics: Optional[List[str]] = Field(default_factory=list)
    main_points: Optional[List[str]] = Field(default_factory=list, description="Key takeaways or main points from the article")
    canonical_url: Optional[HttpUrl] = Field(default=None)
    word_count: Optional[int] = Field(default=None)
    reading_time_minutes: Optional[float] = Field(default=None, description="Estimated reading time in minutes")
    published_at: Optional[datetime] = Field(default=None)
    modified_at: Optional[datetime] = Field(default=None)
    inferred_source: Optional[str] = Field(default=None, description="Detected news source / publisher name")
    schema_org: Optional[Dict[str, Any]] = Field(default=None, description="Raw Schema.org JSON-LD data if available")

    @field_validator("schema_org", mode="before")
    @classmethod
    def _normalize_schema_org(cls, v):
        """Normalize schema_org to dict. If list, take first element."""
        if v is None:
            return v
        if isinstance(v, list):
            # If list, take first dict element
            for item in v:
                if isinstance(item, dict):
                    return item
            return None
        if isinstance(v, dict):
            return v
        return None


class QualitySignals(BaseModel):
    extraction_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    duplicate_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    content_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: Optional[str] = Field(default=None)


class Article(BaseModel):
    id: Optional[str] = Field(default=None, description="Stable id (sha256 or uuid). Computed if missing.")
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    content: str = Field(description="Cleaned article text (all HTML stripped)")
    authors: List[ArticleAuthor] = Field(default_factory=list)
    provenance: Provenance = Field(description="Where/how the article was fetched")
    metadata: ArticleMetadata = Field(default_factory=ArticleMetadata)
    license: LicenseInfo = Field(default_factory=LicenseInfo)
    raw_html: Optional[str] = Field(default=None, description="Original HTML (optional, may be large)")
    extraction: Optional[ExtractionTrace] = Field(default=None)
    chunks: List[ArticleChunk] = Field(default_factory=list)
    embedding: Optional[List[float]] = Field(default_factory=list, description="Optional document-level embedding")
    vector_id: Optional[str] = Field(default=None, description="ID used in vector DB if persisted")
    quality: QualitySignals = Field(default_factory=QualitySignals)
    extras: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    model_config = {
        "title": "Article",
        "json_schema_extra": {
            "example": {
                "id": None,
                "title": "Example: The Rise of Agents",
                "content": "Cleaned text...",
                "provenance": {
                    "source_url": "https://example.com/article/1",
                    "domain": "example.com",
                },
                "metadata": {"language": "en"},
            }
        },
    }

    @field_validator("content", mode="before")
    @classmethod
    def _normalize_content(cls, v: str) -> str:
        """
        Normalize whitespace, remove control chars, trim.
        Keep this light — heavy cleaning should be done in pipeline downstream.
        """
        if v is None:
            return ""
        cleaned = re.sub(r"[\r\n\t]+", " ", v)
        cleaned = re.sub(r"\u00A0", " ", cleaned)
        cleaned = re.sub(r" {2,}", " ", cleaned).strip()
        return cleaned

    @computed_field
    def computed_word_count(self) -> int:
        """Compute word count from content if metadata.word_count missing."""
        if self.metadata and self.metadata.word_count:
            return int(self.metadata.word_count)
        return int(len(WORD_RE.findall(self.content or "")))

    @computed_field
    def computed_token_estimate(self) -> int:
        return estimate_tokens_from_text(self.content or "")

    @computed_field
    def computed_reading_time(self) -> float:
        wc = self.computed_word_count
        return round(wc / 220.0, 2)

    @model_validator(mode='after')
    def _generate_id_if_missing(self):
        """Generate UUID v5 from URL if id is not provided."""
        if not self.id and self.provenance and self.provenance.source_url:
            url_str = str(self.provenance.source_url)
            self.id = str(uuid.uuid5(uuid.NAMESPACE_URL, url_str))
        return self

    def ensure_metadata_counts(self) -> None:
        """Ensure metadata.word_count and reading_time_minutes are filled."""
        wc = self.computed_word_count
        self.metadata.word_count = wc
        self.metadata.reading_time_minutes = self.computed_reading_time

    def chunk_by_char(
        self,
        max_chars: int = 2000,
        overlap_chars: int = 200,
        preserve_headline: bool = True,
    ) -> List[ArticleChunk]:
        """
        Chunk article content into char-based windows with optional overlap.
        Returns list of ArticleChunk and sets self.chunks.
        """
        text = (self.content or "").strip()
        if not text:
            self.chunks = []
            return self.chunks

        if preserve_headline and self.title and text.startswith(self.title):
            body = text[len(self.title) :].strip()
        else:
            body = text

        chunks: List[ArticleChunk] = []
        start = 0
        index = 0
        n = len(body)
        while start < n:
            end = min(n, start + max_chars)
            chunk_text = body[start:end].strip()
            if not chunk_text:
                break
            chunks.append(ArticleChunk.from_text(index=index, text=chunk_text))
            index += 1
            start = end - overlap_chars if end - overlap_chars > start else end

        self.chunks = chunks
        return chunks

    def chunk_by_token_estimate(
        self,
        max_tokens: int = 800,
        overlap_tokens: int = 64,
        sentence_split: bool = True,
    ) -> List[ArticleChunk]:
        """
        Chunk by approximate tokens using whitespace/sentence split heuristics.
        Safer for LLM context windows than char-based chunking.
        """
        text = (self.content or "").strip()
        if not text:
            self.chunks = []
            return self.chunks

        if sentence_split:
            sents = re.split(r"(?<=[.?!])\s+(?=[A-Z0-9\"'“‘])", text)
        else:
            # fallback to word-based splits
            sents = text.split()

        chunks: List[ArticleChunk] = []
        cur_buf: List[str] = []
        cur_tokens = 0
        index = 0

        def flush_chunk(buf: List[str], idx: int):
            chunk_text = " ".join(buf).strip()
            if not chunk_text:
                return None
            return ArticleChunk.from_text(index=idx, text=chunk_text)

        for sent in sents:
            sent_tokens = estimate_tokens_from_text(sent)
            if cur_tokens + sent_tokens > max_tokens and cur_buf:
                ch = flush_chunk(cur_buf, index)
                if ch:
                    chunks.append(ch)
                    index += 1
                if overlap_tokens > 0:
                    overlap_words = int(overlap_tokens / 1.33)
                    words = " ".join(cur_buf).split()
                    overlap_buf = words[-overlap_words:] if overlap_words > 0 else []
                    cur_buf = overlap_buf[:]
                    cur_tokens = estimate_tokens_from_text(" ".join(cur_buf))
                else:
                    cur_buf = []
                    cur_tokens = 0

            cur_buf.append(sent)
            cur_tokens += sent_tokens

        ch = flush_chunk(cur_buf, index)
        if ch:
            chunks.append(ch)

        self.chunks = chunks
        return chunks

    def to_rag_documents(self) -> List[Dict[str, Any]]:
        """
        Convert chunks to documents ready to insert into a vector DB / RAG system.
        Each document contains minimal metadata and chunk text.
        """
        docs = []
        for c in self.chunks:
            docs.append(
                {
                    "id": f"{self.id}-chunk-{c.index}",
                    "text": c.content,
                    "meta": {
                        "article_id": self.id,
                        "title": self.title,
                        "source_url": str(self.provenance.source_url),
                        "index": c.index,
                        "domain": self.provenance.domain,
                    },
                }
            )
        return docs

    def touch_updated(self) -> None:
        self.updated_at = now_utc()

    def summary(self) -> Dict[str, Any]:
        """Return a compact summary for logs or listing APIs."""
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.provenance.domain,
            "url": str(self.provenance.source_url),
            "word_count": self.computed_word_count,
            "tokens_est": self.computed_token_estimate,
            "chunks": len(self.chunks or []),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_html(
        cls, 
        html: str, 
        url: HttpUrl, 
        parser_config: Optional[ParserConfig] = None, 
        output_format: str = "markdown",
        **kwargs
    ) -> "Article":
        """
        Factory method to create an Article from raw HTML.
        It uses the new parser system to extract metadata and content.
        
        Args:
            html: Raw HTML string
            url: Article URL
            parser_config: Optional parser configuration
            output_format: Output format for content ("markdown" or "html"), default "markdown"
            **kwargs: Additional arguments passed to Article constructor
            
        Returns:
            Article instance with extracted content
        """
        if not html or not html.strip():
            raise ArticleCreationError("Cannot create article from empty or invalid HTML.")

        # Validate output_format
        if output_format not in ("markdown", "html"):
            raise ValueError(f"output_format must be 'markdown' or 'html', got: {output_format}")

        # --- Extract Metadata using the new get_metadata function ---
        response_meta = get_metadata(html)

        # --- Extract Content using the new get_parsed_data function ---
        # If a specific parser config is provided, use it.
        parsed_data = {}
        if parser_config:
            parsed_data = get_parsed_data(html, parser_config, base_url=str(url))
            content = parsed_data.get("content", "")
            
            # If content is HTML (still contains tags), clean and convert
            if content and ('<' in content or '>' in content):
                from bs4 import BeautifulSoup
                from llm_scraper.presets import COMMON_CLEANUP_SELECTORS
                
                content_soup = BeautifulSoup(content, "lxml")
                
                # Remove unwanted elements using common cleanup selectors
                # Note: Global cleanup and per-field cleanup already applied in BaseParser
                # This is just a final safety cleanup for any remaining unwanted elements
                for selector in COMMON_CLEANUP_SELECTORS:
                    try:
                        for element in content_soup.select(selector):
                            element.decompose()
                    except Exception:
                        pass  # Ignore selector errors
                
                # Convert to desired output format
                if output_format == "markdown":
                    # Convert cleaned HTML to Markdown
                    from markdownify import markdownify as md
                    content = md(
                        str(content_soup), 
                        heading_style="ATX", 
                        strip=['script', 'style'],
                        bullets='-'
                    )
                    # Clean up extra whitespace
                    content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())
                else:
                    # Extract plain text from cleaned HTML
                    content = content_soup.get_text(separator=" ", strip=True)
                    # Clean up whitespace
                    content = ' '.join(content.split())
        else:
            # Fallback to a simple body extraction if no config is given
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")
                main_content = soup.find("main") or soup.find("article") or soup.find("body")
                content = main_content.get_text(separator=" ", strip=True) if main_content else ""
            except Exception:
                content = ""

        if not content.strip():
            raise ArticleCreationError("Failed to extract meaningful content from HTML.")

        # --- Combine Metadata ---
        # Title is critical, fallback to a default if not found
        title = response_meta.title or "No title found"
        
        # Merge authors from parser config and meta tags
        authors = []
        authors_data = parsed_data.get("authors", [])
        if isinstance(authors_data, list):
            for author_name in authors_data:
                if isinstance(author_name, str) and author_name.strip():
                    authors.append(ArticleAuthor(name=author_name.strip()))
        elif isinstance(authors_data, str) and authors_data.strip():
            authors.append(ArticleAuthor(name=authors_data.strip()))
        
        # Fallback to meta author if no authors from parser
        if not authors and response_meta.author:
            authors.append(ArticleAuthor(name=response_meta.author))
        
        # Merge published_at and other metadata, giving priority to parser config
        published_at = parsed_data.get("date_published") or response_meta.date_published
        modified_at = parsed_data.get("date_modified") or response_meta.date_modified
        tags = parsed_data.get("tags", []) or response_meta.tags or []
        topics = parsed_data.get("topics", []) or response_meta.topics or []
        main_points = parsed_data.get("main_points", []) or []

        try:
            article = cls(
                title=title,
                description=response_meta.description,
                content=content,
                authors=authors,
                provenance=Provenance(source_url=url, domain=urlparse(str(url)).netloc),
                metadata=ArticleMetadata(
                    language=response_meta.language,
                    tags=tags,
                    topics=topics,
                    main_points=main_points,
                    canonical_url=response_meta.canonical,
                    published_at=published_at,
                    modified_at=modified_at,
                    schema_org=response_meta.schema_org,
                ),
                raw_html=html,
                **kwargs,
            )
            article.ensure_metadata_counts()
            return article
        except ValidationError as e:
            raise ArticleCreationError(f"Failed to validate article data: {e}") from e
