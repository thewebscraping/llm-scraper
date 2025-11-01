from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    ValidationError,
    computed_field,
    field_validator,
)

from .exceptions import ArticleCreationError
from .models.selector import ParserConfig
from .parsers.base import get_metadata, get_parsed_data


_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def estimate_tokens_from_text(text: str, avg_token_per_word: float = 1.33) -> int:
    """
    Heuristic token estimate: average tokens per word.
    Default 1.33 approximates subword tokenization (fast & safe).
    You can replace with real tokenizer in pipeline.
    """
    if not text:
        return 0
    words = len(_WORD_RE.findall(text))
    return int(math.ceil(words * avg_token_per_word))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    fetched_at: datetime = Field(default_factory=_now_utc, description="When fetch occurred")


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
        wc = len(_WORD_RE.findall(text))
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
    canonical_url: Optional[HttpUrl] = Field(default=None)
    word_count: Optional[int] = Field(default=None)
    reading_time_minutes: Optional[float] = Field(default=None, description="Estimated reading time in minutes")
    published_at: Optional[datetime] = Field(default=None)
    modified_at: Optional[datetime] = Field(default=None)
    inferred_source: Optional[str] = Field(default=None, description="Detected news source / publisher name")


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
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)

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
        return int(len(_WORD_RE.findall(self.content or "")))

    @computed_field
    def computed_token_estimate(self) -> int:
        return estimate_tokens_from_text(self.content or "")

    @computed_field
    def computed_reading_time(self) -> float:
        wc = self.computed_word_count
        return round(wc / 220.0, 2)

    @field_validator("id", mode="before")
    @classmethod
    def _compute_id_if_missing(cls, v, info):
        """
        If id not provided, compute as sha256(source_url + first 200 chars content).
        This provides determinism across runs for same URL+content snapshot.
        """
        if v:
            return v
        values = info.data or {}
        provenance: Optional[Provenance] = values.get("provenance")
        content: Optional[str] = values.get("content") or ""
        url_part = ""
        if provenance and getattr(provenance, "source_url", None):
            url_part = str(provenance.source_url)
        seed = url_part + "|" + (content[:512] if content else "")
        return sha256_hex(seed)

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
        self.updated_at = _now_utc()

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
        cls, html: str, url: HttpUrl, parser_config: Optional[ParserConfig] = None, **kwargs
    ) -> "Article":
        """
        Factory method to create an Article from raw HTML.
        It uses the new parser system to extract metadata and content.
        """
        if not html or not html.strip():
            raise ArticleCreationError("Cannot create article from empty or invalid HTML.")

        # --- Extract Metadata using the new get_metadata function ---
        response_meta = get_metadata(html)

        # --- Extract Content using the new get_parsed_data function ---
        # If a specific parser config is provided, use it.
        if parser_config:
            parsed_data = get_parsed_data(html, parser_config)
            content = parsed_data.get("content", "")
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

        try:
            article = cls(
                title=title,
                description=response_meta.description,
                content=content,
                provenance=Provenance(source_url=url, domain=urlparse(str(url)).netloc),
                metadata=ArticleMetadata(
                    language=response_meta.language,
                    tags=response_meta.tags,
                    topics=response_meta.topics,
                    canonical_url=response_meta.canonical,
                    published_at=response_meta.date_published,
                    modified_at=response_meta.date_modified,
                ),
                raw_html=html,
                **kwargs,
            )
            article.ensure_metadata_counts()
            return article
        except ValidationError as e:
            raise ArticleCreationError(f"Failed to validate article data: {e}") from e
