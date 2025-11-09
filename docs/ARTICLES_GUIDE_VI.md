# Hướng Dẫn Kiến Trúc Module Article

**Phiên bản:** 1.0  
**Cập nhật:** 9 tháng 11, 2025

## Mục Lục

1. [Tổng Quan](#tổng-quan)
2. [Sơ Đồ Kiến Trúc](#sơ-đồ-kiến-trúc)
3. [Các Model Cốt Lõi](#các-model-cốt-lõi)
4. [Hàm Tiện Ích](#hàm-tiện-ích)
5. [Validators & Computed Fields](#validators--computed-fields)
6. [Factory Methods](#factory-methods)
7. [Chiến Lược Chunking](#chiến-lược-chunking)
8. [Tích Hợp RAG](#tích-hợp-rag)
9. [Ví Dụ Sử Dụng](#ví-dụ-sử-dụng)
10. [Best Practices](#best-practices)

---

## Tổng Quan

Module `articles.py` cung cấp một data model toàn diện để trích xuất, lưu trữ và tích hợp bài viết web vào pipeline RAG (Retrieval-Augmented Generation). Module được xây dựng trên Pydantic để đảm bảo validation mạnh mẽ và bao gồm các tính năng nâng cao như:

- **Tự động trích xuất metadata** từ HTML
- **Chiến lược chunking linh hoạt** cho context window của LLM
- **Theo dõi nguồn gốc dữ liệu** (provenance tracking)
- **Tín hiệu chất lượng** để đánh giá nội dung
- **Tích hợp Schema.org** cho dữ liệu có cấu trúc
- **Chuyển đổi sang định dạng RAG** sẵn sàng sử dụng

---

## Sơ Đồ Kiến Trúc

```
┌─────────────────────────────────────────────────────────────┐
│                        Article Model                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Các Trường Cốt Lõi                                   │   │
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
│  │ Computed Fields (Tự động tính toán)                  │   │
│  │  - computed_word_count                               │   │
│  │  - computed_token_estimate                           │   │
│  │  - computed_reading_time                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Methods (Phương thức)                                │   │
│  │  - from_html() [Factory]                             │   │
│  │  - chunk_by_char()                                   │   │
│  │  - chunk_by_token_estimate()                         │   │
│  │  - to_rag_documents()                                │   │
│  │  - summary()                                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Các Model Cốt Lõi

### 1. **ArticleAuthor**

Đại diện cho tác giả bài viết với thông tin liên hệ tùy chọn.

```python
class ArticleAuthor(BaseModel):
    name: str                          # Bắt buộc: Tên hiển thị của tác giả
    email: Optional[str]               # Tùy chọn: Email liên hệ
    profile_url: Optional[HttpUrl]     # Tùy chọn: Link profile/mạng xã hội
    affiliation: Optional[str]         # Tùy chọn: Tổ chức/đơn vị
```

**Trường hợp sử dụng:**
- Nhiều tác giả cho một bài viết
- Liên kết đến profile tác giả
- Theo dõi nguồn gốc nội dung

**Ví dụ:**
```python
author = ArticleAuthor(
    name="Nguyễn Văn A",
    email="nguyenvana@example.com",
    profile_url="https://example.com/tac-gia/nguyen-van-a",
    affiliation="Báo Công Nghệ"
)
```

---

### 2. **CrawlerInfo**

Theo dõi thông tin về cách và khi nào bài viết được lấy về.

```python
class CrawlerInfo(BaseModel):
    crawler_name: Optional[str]        # VD: "llm-scraper/0.1.1"
    user_agent: Optional[str]          # User-Agent string sử dụng
    ip: Optional[str]                  # Địa chỉ IP của máy fetch
    fetch_duration_ms: Optional[int]   # Thời gian fetch (milliseconds)
    fetch_status: Optional[int]        # HTTP status code (200, 404, etc.)
    fetched_at: datetime               # Tự động set thời gian UTC hiện tại
```

**Trường hợp sử dụng:**
- Debug các vấn đề khi fetch
- Giám sát hiệu suất
- Tuân thủ quy định (công khai User-Agent)

---

### 3. **Provenance**

Theo dõi hoàn chỉnh nguồn gốc dữ liệu của bài viết.

```python
class Provenance(BaseModel):
    source_url: HttpUrl                      # Bắt buộc: URL chính thức
    domain: Optional[str]                    # VD: "example.com"
    original_html_saved: bool = False        # Flag lưu HTML gốc
    snapshot_path: Optional[str]             # Đường dẫn đến HTML đã lưu
    tls_ja3: Optional[str]                   # TLS fingerprint
    crawler: Optional[CrawlerInfo]           # Metadata về quá trình fetch
```

**Tính năng chính:**
- **ID xác định (Deterministic)**: URL → UUID v5 mapping
- **Hỗ trợ snapshot**: Lưu HTML gốc để audit
- **Theo dõi bảo mật**: TLS/JA3 fingerprints

**Ví dụ:**
```python
provenance = Provenance(
    source_url="https://vnexpress.net/bai-viet-123",
    domain="vnexpress.net",
    original_html_saved=True,
    snapshot_path="s3://bucket/snapshots/bai-viet-123.html",
    crawler=CrawlerInfo(
        crawler_name="llm-scraper/1.0",
        fetch_status=200,
        fetch_duration_ms=1234
    )
)
```

---

### 4. **ArticleMetadata**

Metadata phong phú được trích xuất từ bài viết và meta tags.

```python
class ArticleMetadata(BaseModel):
    language: Optional[str]                  # Mã ISO-639-1 (VD: "vi")
    tags: List[str]                          # Tags/từ khóa bài viết
    topics: List[str]                        # Chủ đề phân loại
    canonical_url: Optional[HttpUrl]         # URL chính thức
    word_count: Optional[int]                # Tổng số từ
    reading_time_minutes: Optional[float]    # Thời gian đọc ước tính
    published_at: Optional[datetime]         # Ngày xuất bản
    modified_at: Optional[datetime]          # Ngày sửa đổi cuối cùng
    inferred_source: Optional[str]           # Tên nhà xuất bản
    schema_org: Optional[Dict[str, Any]]     # Dữ liệu Schema.org JSON-LD thô
```

**Tích hợp Schema.org:**
Trường `schema_org` lưu trữ toàn bộ dữ liệu JSON-LD từ các thẻ `<script type="application/ld+json">`, giữ nguyên tất cả dữ liệu có cấu trúc để xử lý sau.

**Ví dụ:**
```python
metadata = ArticleMetadata(
    language="vi",
    tags=["AI", "Học Máy", "GPT-4"],
    topics=["Công Nghệ", "Trí Tuệ Nhân Tạo"],
    word_count=1500,
    reading_time_minutes=6.8,
    published_at=datetime(2024, 11, 1, 10, 0, 0, tzinfo=timezone.utc),
    schema_org={
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Tin Tức Mới Về AI",
        "datePublished": "2024-11-01T10:00:00Z"
    }
)
```

---

### 5. **ArticleChunk**

Đại diện cho một đoạn (chunk) nội dung bài viết cho hệ thống RAG.

```python
class ArticleChunk(BaseModel):
    index: int                           # Index tuần tự (bắt đầu từ 0)
    content: str                         # Text đã làm sạch
    char_length: int                     # Độ dài ký tự
    word_count: int                      # Số từ
    token_estimate: int                  # Số token ước tính
    embedding: Optional[List[float]]     # Vector embedding (nếu đã tính)
    metadata: Dict[str, Any]             # Metadata riêng cho chunk
```

**Factory Method:**
```python
@classmethod
def from_text(cls, index: int, text: str) -> "ArticleChunk":
    """Tự động tính toán tất cả metrics từ text thô."""
```

**Ví dụ:**
```python
chunk = ArticleChunk.from_text(
    index=0,
    text="Đây là đoạn đầu tiên của bài viết..."
)
# Tự động set: char_length, word_count, token_estimate
```

---

### 6. **QualitySignals**

Các metrics đánh giá chất lượng nội dung.

```python
class QualitySignals(BaseModel):
    extraction_confidence: Optional[float]   # 0.0-1.0: Chất lượng trích xuất
    duplicate_score: Optional[float]         # 0.0-1.0: Khả năng trùng lặp
    content_quality: Optional[float]         # 0.0-1.0: Chất lượng tổng thể
    notes: Optional[str]                     # Ghi chú dạng text
```

**Trường hợp sử dụng:**
- Lọc nội dung chất lượng thấp
- Ưu tiên những bài trích xuất tin cậy cao
- Debug các vấn đề trích xuất

---

### 7. **Article** (Model Chính)

Model đại diện hoàn chỉnh cho một bài viết.

```python
class Article(BaseModel):
    # Nội Dung Cốt Lõi
    id: Optional[str]                        # UUID v5 tự động từ URL
    title: Optional[str]                     # Tiêu đề bài viết
    description: Optional[str]               # Meta description
    content: str                             # Text đã làm sạch (bỏ HTML)
    
    # Dữ Liệu Có Cấu Trúc
    authors: List[ArticleAuthor]             # Thông tin tác giả
    provenance: Provenance                   # Nguồn gốc dữ liệu
    metadata: ArticleMetadata                # Metadata phong phú
    license: LicenseInfo                     # Thông tin bản quyền
    
    # Dữ Liệu Tùy Chọn
    raw_html: Optional[str]                  # HTML gốc
    extraction: Optional[ExtractionTrace]    # Debug info trích xuất
    chunks: List[ArticleChunk]               # Các đoạn nội dung cho RAG
    embedding: Optional[List[float]]         # Embedding cấp document
    vector_id: Optional[str]                 # ID trong vector DB
    quality: QualitySignals                  # Metrics chất lượng
    extras: Dict[str, Any]                   # Trường tùy chỉnh
    
    # Timestamps
    created_at: datetime                     # Tự động set UTC hiện tại
    updated_at: datetime                     # Tự động set UTC hiện tại
```

---

## Hàm Tiện Ích

Tất cả các hàm tiện ích đã được refactor vào `utils/` để tổ chức code tốt hơn:

### Từ `utils/text.py`:

```python
WORD_RE = re.compile(r"\w+", re.UNICODE)     # Regex nhận diện từ Unicode

def estimate_tokens_from_text(text: str, avg_token_per_word: float = 1.33) -> int:
    """Ước tính nhanh số token (1.33 tokens/từ cho GPT models)."""

def count_words(text: str) -> int:
    """Đếm số từ sử dụng unicode-aware regex."""

def sha256_hex(value: str) -> str:
    """Tạo SHA-256 hash (cho việc phát hiện trùng lặp)."""
```

### Từ `utils/datetime.py`:

```python
def now_utc() -> datetime:
    """Lấy datetime UTC hiện tại với timezone awareness."""
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
    Chuẩn hóa khoảng trắng, loại bỏ ký tự điều khiển, trim.
    - Thay thế \\r\\n\\t bằng khoảng trắng
    - Loại bỏ non-breaking spaces (\\u00A0)
    - Gộp nhiều khoảng trắng thành một
    - Xóa khoảng trắng đầu/cuối
    """
```

**Input:**
```python
"Xin chào\\n\\nThế giới  \\t  Nhiều   Khoảng trắng\\u00A0Ở đây"
```

**Output:**
```python
"Xin chào Thế giới Nhiều Khoảng trắng Ở đây"
```

---

### Computed Fields

Computed fields được **tự động tính toán** và cache. Không cần lưu vào database nhưng vẫn được bao gồm khi serialize.

#### 1. **`computed_word_count`**

```python
@computed_field
def computed_word_count(self) -> int:
    """
    Ưu tiên:
    1. Dùng metadata.word_count nếu có
    2. Nếu không, đếm từ trong content dùng WORD_RE
    """
```

#### 2. **`computed_token_estimate`**

```python
@computed_field
def computed_token_estimate(self) -> int:
    """Ước tính token dùng heuristic 1.33 tokens/từ."""
```

#### 3. **`computed_reading_time`**

```python
@computed_field
def computed_reading_time(self) -> float:
    """
    Ước tính thời gian đọc (phút).
    Công thức: word_count / 220 từ mỗi phút (tốc độ đọc trung bình)
    """
```

**Ví dụ:**
```python
article = Article(content="..." * 1000)  # ~1000 từ
print(article.computed_word_count)       # 1000
print(article.computed_token_estimate)   # 1330
print(article.computed_reading_time)     # 4.55 (phút)
```

---

### Model Validators

#### **Tự Động Tạo ID** (`_generate_id_if_missing`)

```python
@model_validator(mode='after')
def _generate_id_if_missing(self):
    """
    Tạo UUID v5 xác định từ source URL nếu ID chưa được cung cấp.
    Sử dụng uuid.NAMESPACE_URL để đảm bảo nhất quán.
    """
```

**Ví dụ:**
```python
article = Article(
    content="...",
    provenance=Provenance(source_url="https://vnexpress.net/bai-viet-123")
)
# Tự động tạo: id = "a1b2c3d4-..."  (cùng URL = cùng UUID)
```

---

## Factory Methods

### `Article.from_html()`

Factory method chính để tạo article từ HTML thô.

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
    Factory method để tạo Article từ HTML thô.
    
    Quy trình xử lý:
    1. Trích xuất metadata dùng get_metadata(html)
       - OpenGraph tags
       - Twitter Card tags
       - Schema.org JSON-LD
       - Meta tags chuẩn
    
    2. Trích xuất nội dung dùng get_parsed_data(html, parser_config)
       - Nếu có parser_config: dùng selectors theo domain
       - Nếu không: fallback sang <main>, <article>, hoặc <body>
    
    3. Gộp metadata từ cả hai nguồn
       - Ưu tiên: parser_config > meta tags
       - Gộp authors, tags, topics
    
    4. Tạo Article instance với validation
    
    5. Gọi ensure_metadata_counts() để điền computed fields
    
    Args:
        html: Nội dung HTML thô
        url: URL bài viết (dùng cho provenance và tạo ID)
        parser_config: Cấu hình parser theo domain (tùy chọn)
        **kwargs: Các trường bổ sung cho Article constructor
    
    Returns:
        Article instance đã được validate
    
    Raises:
        ArticleCreationError: Nếu HTML rỗng hoặc trích xuất nội dung thất bại
    """
```

**Ví dụ 1: Với ParserConfig**

```python
from llm_scraper.models.selector import ParserConfig, ElementSelector

config = ParserConfig(
    domain="vnexpress.net",
    content=ElementSelector(css_selector="article.fck_detail"),
    title=ElementSelector(css_selector="h1.title-detail"),
    authors=ElementSelector(css_selector="p.author_mail strong", all=True),
    date_published=ElementSelector(css_selector="span.date", attribute="datetime"),
    tags=ElementSelector(css_selector="li.item-tag a", all=True)
)

article = Article.from_html(
    html=html_content,
    url="https://vnexpress.net/bai-viet-123",
    parser_config=config
)
```

**Ví dụ 2: Chế Độ Fallback (Không Config)**

```python
article = Article.from_html(
    html=html_content,
    url="https://vnexpress.net/bai-viet-123"
)
# Sử dụng: get_metadata() cho meta tags + trích xuất <main>/<article>/<body>
```

---

## Chiến Lược Chunking

Article model cung cấp hai chiến lược chunking cho hệ thống RAG:

### 1. **Chunking Theo Ký Tự** (`chunk_by_char`)

```python
def chunk_by_char(
    self,
    max_chars: int = 2000,
    overlap_chars: int = 200,
    preserve_headline: bool = True,
) -> List[ArticleChunk]:
    """
    Chia nội dung bài viết thành các cửa sổ ký tự cố định.
    
    Thuật toán:
    1. Tùy chọn loại bỏ title khỏi đầu content
    2. Tạo các chunk có độ dài max_chars
    3. Áp dụng overlap_chars giữa các chunks
    4. Tạo ArticleChunk instances với metadata
    
    Args:
        max_chars: Số ký tự tối đa mỗi chunk
        overlap_chars: Số ký tự chồng lấn giữa các chunks
        preserve_headline: Loại bỏ title khỏi content nếu nó xuất hiện ở đầu
    
    Returns:
        List các ArticleChunk objects (cũng set self.chunks)
    """
```

**Trường hợp sử dụng:**
- Kích thước chunk đơn giản, dễ dự đoán
- Khi số ký tự quan trọng hơn ranh giới ngữ nghĩa

**Ví dụ:**
```python
article = Article.from_html(html, url)
chunks = article.chunk_by_char(
    max_chars=1500,
    overlap_chars=150,
    preserve_headline=True
)
print(f"Đã tạo {len(chunks)} chunks")
for chunk in chunks[:3]:
    print(f"Chunk {chunk.index}: {chunk.char_length} ký tự, ~{chunk.token_estimate} tokens")
```

---

### 2. **Chunking Theo Token** (`chunk_by_token_estimate`)

**Được khuyến nghị cho LLM context windows** - chính xác hơn chunking theo ký tự.

```python
def chunk_by_token_estimate(
    self,
    max_tokens: int = 800,
    overlap_tokens: int = 64,
    sentence_split: bool = True,
) -> List[ArticleChunk]:
    """
    Chia theo số token ước tính sử dụng ranh giới câu/từ.
    
    Thuật toán:
    1. Chia theo câu (regex) hoặc từ
    2. Xây dựng chunks cho đến khi đạt max_tokens
    3. Áp dụng overlap_tokens giữa các chunks
    4. Xử lý edge cases (câu quá dài)
    
    Args:
        max_tokens: Số token tối đa ước tính mỗi chunk
        overlap_tokens: Số token chồng lấn giữa các chunks
        sentence_split: Dùng ranh giới câu (True) hoặc ranh giới từ (False)
    
    Returns:
        List các ArticleChunk objects (cũng set self.chunks)
    """
```

**Regex Chia Câu:**
```python
r"(?<=[.?!])\s+(?=[A-Z0-9\"'"'])"
# Khớp: dấu chấm/hỏi/than + khoảng trắng + chữ hoa
```

**Trường hợp sử dụng:**
- LLM context windows (giữ dưới giới hạn token)
- Chunking ngữ nghĩa (ranh giới câu)
- RAG retrieval (chunks mạch lạc hơn)

**Ví dụ:**
```python
article = Article.from_html(html, url)
chunks = article.chunk_by_token_estimate(
    max_tokens=512,      # Kích thước chunk an toàn cho GPT-4
    overlap_tokens=50,   # Chồng lấn để duy trì ngữ cảnh
    sentence_split=True  # Giữ nguyên ranh giới câu
)

# Thêm embeddings vào chunks
for chunk in chunks:
    chunk.embedding = get_embedding(chunk.content)  # Hàm embedding của bạn

# Sẵn sàng insert vào vector DB
docs = article.to_rag_documents()
```

---

## Tích Hợp RAG

### **`to_rag_documents()`**

Chuyển đổi chunks sang documents sẵn sàng cho vector databases.

```python
def to_rag_documents(self) -> List[Dict[str, Any]]:
    """
    Chuyển đổi chunks sang documents để insert vào vector DB.
    
    Định dạng output:
    [
        {
            "id": "article-uuid-chunk-0",
            "text": "nội dung chunk...",
            "meta": {
                "article_id": "article-uuid",
                "title": "Tiêu Đề Bài Viết",
                "source_url": "https://...",
                "index": 0,
                "domain": "example.com"
            }
        },
        ...
    ]
    """
```

**Ví dụ Tích Hợp:**

#### Pinecone:
```python
import pinecone

article = Article.from_html(html, url)
article.chunk_by_token_estimate(max_tokens=512)

# Tạo embeddings
for chunk in article.chunks:
    chunk.embedding = model.encode(chunk.content)

# Chuẩn bị cho Pinecone
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

## Ví Dụ Sử Dụng

### Ví dụ 1: Tạo Article Cơ Bản

```python
from llm_scraper.articles import Article
from pydantic import HttpUrl

# Tạo article thủ công
article = Article(
    title="Hiểu về LLMs",
    content="Các mô hình ngôn ngữ lớn đang biến đổi AI...",
    provenance=Provenance(
        source_url=HttpUrl("https://example.com/bai-viet/1")
    )
)

# Các trường tự động tạo
print(article.id)                      # UUID v5 từ URL
print(article.computed_word_count)     # 7
print(article.computed_token_estimate) # 9
print(article.computed_reading_time)   # 0.03 phút
```

---

### Ví dụ 2: Từ HTML với Config

```python
import httpx
from llm_scraper.articles import Article
from llm_scraper.models.selector import ParserConfig

# Fetch HTML
response = httpx.get("https://vnexpress.net/bai-viet-123")
html = response.text

# Load config theo domain
config = ParserConfig.from_json_file("configs/vi/v/vnexpress.net.json")

# Tạo article
article = Article.from_html(
    html=html,
    url=response.url,
    parser_config=config
)

# Truy cập dữ liệu có cấu trúc
print(f"Tiêu đề: {article.title}")
print(f"Tác giả: {[a.name for a in article.authors]}")
print(f"Xuất bản: {article.metadata.published_at}")
print(f"Tags: {article.metadata.tags}")
print(f"Schema.org: {article.metadata.schema_org}")
```

---

### Ví dụ 3: RAG Pipeline

```python
from llm_scraper.articles import Article
from sentence_transformers import SentenceTransformer

# Load embedding model
embedder = SentenceTransformer('bkai-foundation-models/vietnamese-bi-encoder')

# Tạo article
article = Article.from_html(html, url)

# Chunk cho RAG (512 tokens tối đa, 50 token chồng lấn)
chunks = article.chunk_by_token_estimate(
    max_tokens=512,
    overlap_tokens=50,
    sentence_split=True
)

# Tạo embeddings
for chunk in chunks:
    chunk.embedding = embedder.encode(chunk.content).tolist()

# Chuyển sang RAG documents
rag_docs = article.to_rag_documents()

# Insert vào vector DB (pseudo-code)
vector_db.insert(rag_docs)

# Query sau này
query_embedding = embedder.encode("LLM là gì?")
results = vector_db.search(query_embedding, top_k=5)
```

---

### Ví dụ 4: Lọc Chất Lượng

```python
articles = []
for url in urls:
    html = fetch(url)
    article = Article.from_html(html, url)
    
    # Set quality signals
    article.quality.extraction_confidence = calculate_confidence(article)
    article.quality.content_quality = assess_quality(article.content)
    
    # Lọc chất lượng thấp
    if article.quality.extraction_confidence > 0.7:
        if article.computed_word_count >= 300:
            articles.append(article)

print(f"Giữ lại {len(articles)} bài viết chất lượng cao")
```

---

### Ví dụ 5: Xử Lý Batch

```python
from concurrent.futures import ThreadPoolExecutor
import httpx

def process_url(url: str) -> Article:
    """Fetch và parse bài viết từ URL."""
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        
        article = Article.from_html(
            html=response.text,
            url=response.url
        )
        article.chunk_by_token_estimate(max_tokens=512)
        return article
    except Exception as e:
        print(f"Lỗi xử lý {url}: {e}")
        return None

# Xử lý 100 URLs song song
urls = [...]  # Danh sách URL của bạn
with ThreadPoolExecutor(max_workers=10) as executor:
    articles = list(executor.map(process_url, urls))

# Lọc thành công
articles = [a for a in articles if a is not None]
print(f"Đã xử lý {len(articles)} bài viết")
```

---

## Best Practices

### 1. **Luôn Dùng `from_html()` Factory**

✅ **Tốt:**
```python
article = Article.from_html(html, url, parser_config=config)
```

❌ **Không tốt:**
```python
article = Article(content=extract_content(html), ...)  # Trích xuất thủ công
```

**Tại sao:** `from_html()` xử lý trích xuất metadata, validation và error handling.

---

### 2. **Chọn Chiến Lược Chunking Phù Hợp**

| Trường hợp | Chiến lược | Cài đặt |
|----------|----------|----------|
| RAG chung | `chunk_by_token_estimate` | `max_tokens=512, overlap_tokens=50` |
| Models context dài | `chunk_by_token_estimate` | `max_tokens=2000, overlap_tokens=100` |
| Giới hạn ký tự chính xác | `chunk_by_char` | `max_chars=1500, overlap_chars=150` |
| Ngữ nghĩa mạch lạc | `chunk_by_token_estimate` | `sentence_split=True` |

---

### 3. **Validate Chất Lượng Trích Xuất**

```python
article = Article.from_html(html, url)

# Kiểm tra chất lượng nội dung
if len(article.content) < 200:
    print("Cảnh báo: Nội dung ngắn đáng ngờ")

if article.computed_word_count < 100:
    print("Cảnh báo: Bài viết rất ngắn")

if not article.title:
    print("Cảnh báo: Không trích xuất được tiêu đề")

if not article.authors:
    print("Cảnh báo: Không tìm thấy tác giả")
```

---

### 4. **Giữ Lại Raw HTML Để Audit**

```python
article = Article.from_html(
    html=html,
    url=url,
    raw_html=html  # Lưu HTML gốc
)

article.provenance.original_html_saved = True
article.provenance.snapshot_path = f"s3://bucket/{article.id}.html"
```

---

### 5. **Dùng Computed Fields, Đừng Lưu Trùng Lặp**

✅ **Tốt:**
```python
article = Article.from_html(html, url)
# Dùng computed fields trực tiếp
reading_time = article.computed_reading_time
```

❌ **Không tốt:**
```python
article.metadata.reading_time_minutes = calculate_reading_time(article.content)
# Trùng lặp - đã tự động tính rồi
```

---

### 6. **Xử Lý Lỗi Một Cách Graceful**

```python
from llm_scraper.exceptions import ArticleCreationError

try:
    article = Article.from_html(html, url, parser_config=config)
except ArticleCreationError as e:
    print(f"Không tạo được article: {e}")
    # Fallback sang trích xuất đơn giản hơn hoặc bỏ qua
```

---

### 7. **Batch Insert RAG Documents**

```python
# Thu thập tất cả documents trước
all_docs = []
for article in articles:
    article.chunk_by_token_estimate()
    all_docs.extend(article.to_rag_documents())

# Batch insert (hiệu quả hơn)
vector_db.insert_batch(all_docs, batch_size=100)
```

---

## Tóm Tắt

Module `articles.py` cung cấp:

- ✅ **Data models mạnh mẽ** với Pydantic validation
- ✅ **Tự động trích xuất metadata** từ HTML
- ✅ **Chunking linh hoạt** cho hệ thống RAG
- ✅ **Theo dõi nguồn gốc** cho data lineage
- ✅ **Tín hiệu chất lượng** để lọc nội dung
- ✅ **Tích hợp Schema.org** cho dữ liệu có cấu trúc
- ✅ **Output sẵn sàng cho RAG** cho vector databases

**Điểm Chính:**

1. Dùng `Article.from_html()` để chuyển đổi HTML → Article
2. Chọn chiến lược chunking dựa trên LLM context window
3. Tận dụng computed fields cho tính toán tự động
4. Theo dõi provenance để tuân thủ và debug
5. Lọc theo quality signals trước khi RAG ingestion

---

**Có câu hỏi?**  
Xem [tài liệu chính](README.md) hoặc mở issue trên GitHub.
