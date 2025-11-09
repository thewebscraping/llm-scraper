from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup
from pydantic import (
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
)
from .base import BaseModel, AliasGenerator
from ..utils.normalization import normalize_datetime, normalize_list_str, normalize_str, normalize_url

__all__ = (
    "MetaGEO",
    "Meta",
    "MetaDatetime",
    "OpenGraphArticle",
    "OpenGraphAudio",
    "OpenGraphBook",
    "OpenGraphImage",
    "OpenGraphMusic",
    "OpenGraphMusicAlbum",
    "OpenGraphMusicSong",
    "OpenGraphVideo",
    "OpenGraphMetadata",
    "OpenProfile",
    "ResponseMeta",
    "TwitterCard",
)


class BaseMeta(BaseModel):
    _meta_sep: str = ":"

    @classmethod
    def get_meta_kwargs(cls, fields, suffix: str = None, is_camel_case: bool = False):
        def _get_field(field):
            return AliasGenerator.to_camel_case(field) if is_camel_case else field

        attrs = []
        prefix = cls.get_private_field("_meta_prefix")
        if prefix:
            attrs.append(prefix)

        if suffix:
            attrs.append(suffix)

        sep = cls.get_private_field("_meta_sep")
        return {field: sep.join([attr for attr in attrs if attr != field] + [_get_field(field)]) for field in fields}

    @classmethod
    def to_meta_kwargs(cls) -> dict:
        base_model_fields, subs = [], []
        for field, info in cls.model_fields.items():
            sub_fields = getattr(info.annotation, "model_fields", None)
            if sub_fields:
                subs.append((field, info.annotation))
            else:
                base_model_fields.append(field)

        is_camel_case = cls.get_private_field("_meta_camelcase")
        kwargs = cls.get_meta_kwargs(base_model_fields, is_camel_case=is_camel_case)
        for field, sub_class in subs:
            if not issubclass(sub_class, BaseMeta):
                continue

            is_camel_case = sub_class.get_private_field("_meta_camelcase")
            model_fields = sub_class.model_fields
            suffix = sub_class.get_private_field("_meta_prefix")
            kwargs[field] = cls.get_meta_kwargs(model_fields, suffix, is_camel_case)

        return kwargs


class OpenGraphArticle(BaseMeta):
    author: Optional[str] = None
    expiration_time: Optional[str] = None
    modified_time: Optional[str] = None
    published_time: Optional[str] = None
    publisher: Optional[str] = None
    section: Optional[str] = None
    tag: Optional[str] = None


class OpenGraphAudio(BaseMeta):
    audio: Optional[str] = None
    secure_url: Optional[str] = None
    type: Optional[str] = None


class OpenGraphBook(BaseMeta):
    author: Optional[str] = None
    isbn: Optional[str] = None
    release_date: Optional[str] = None
    tag: Optional[str] = None


class OpenGraphImage(BaseMeta):
    image: Optional[str] = None
    secure_url: Optional[str] = None
    type: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None
    alt: Optional[str] = None

    @property
    def url(self) -> Optional[str]:
        return self.image or self.secure_url


class OpenGraphMusicAlbum(BaseMeta):
    album: Optional[str] = None
    disc: Optional[str] = None
    track: Optional[str] = None


class OpenGraphMusicSong(BaseMeta):
    song: Optional[str] = None
    disc: Optional[str] = None
    track: Optional[str] = None


class OpenGraphMusic(BaseMeta):
    album: Optional[OpenGraphMusicAlbum] = None
    song: Optional[OpenGraphMusicSong] = None
    musician: Optional[str] = None
    release_date: Optional[str] = None


class OpenGraphVideo(BaseMeta):
    actor: Optional[str] = None
    director: Optional[str] = None
    duration: Optional[str] = None
    release_date: Optional[str] = None
    series: Optional[str] = None
    tag: Optional[str] = None
    writer: Optional[str] = None


class OpenProfile(BaseMeta):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    gender: Optional[str] = None


class OpenGraphMetadata(BaseMeta):
    author: Optional[str] = None
    description: Optional[str] = None
    image: Optional[OpenGraphImage] = None
    site_name: Optional[str] = None
    title: Optional[str] = None
    url: Optional[HttpUrl] = None
    locale: Optional[str] = None


class MetaGEO(BaseMeta):
    placename: Optional[str] = None
    position: Optional[str] = None
    region: Optional[str] = None


class MetaImage(BaseMeta):
    url: Optional[str] = None
    type: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None
    alt: Optional[str] = None


class TwitterCard(BaseMeta):
    card: Optional[str] = None
    creator: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    site: Optional[str] = None
    url: Optional[str] = None


class MetaDatetime(BaseMeta):
    date_created: Optional[Union[datetime, str]] = None
    date_modified: Optional[Union[datetime, str]] = None
    date_published: Optional[Union[datetime, str]] = None

    @field_validator("date_created", "date_modified", "date_published", mode="before")
    @classmethod
    def _prepare_dates(cls, v):
        return normalize_datetime(v)

class Meta(BaseMeta):
    _topics_cache: Optional[List[str]] = None
    _tags_cache: Optional[List[str]] = None

    author: Optional[str] = None
    canonical: Optional[str] = None
    description: Optional[str] = None
    geo: Optional[MetaGEO] = None
    keywords: Optional[str] = None
    locale: Optional[str] = None
    news_keywords: Optional[str] = None
    section: Optional[str] = None
    title: Optional[str] = None
    article: Optional[OpenGraphArticle] = None
    datetime: Optional[MetaDatetime] = None
    open_graph: Optional[OpenGraphMetadata] = None
    twitter: Optional[TwitterCard] = None

    @property
    def image(self) -> Optional[MetaImage]:
        if self.open_graph and self.open_graph.image:
            return MetaImage(
                url=self.open_graph.image.url,
                type=self.open_graph.image.type,
                height=self.open_graph.image.height,
                width=self.open_graph.image.width,
                alt=self.open_graph.image.alt,
            )
        if self.twitter and self.twitter.image:
            return MetaImage(url=self.twitter.image)
        return None

    @property
    def date_published(self) -> Optional[datetime]:
        if self.article and getattr(self.article, "published_time", None):
            return normalize_datetime(self.article.published_time)
        if self.datetime and getattr(self.datetime, "date_published", None):
            return normalize_datetime(self.datetime.date_published)
        if self.datetime and getattr(self.datetime, "date_created", None):
            return normalize_datetime(self.datetime.date_created)
        return None

    @property
    def date_modified(self) -> Optional[datetime]:
        if self.article and getattr(self.article, "modified_time", None):
            return normalize_datetime(self.article.modified_time)
        if self.datetime and getattr(self.datetime, "date_modified", None):
            return normalize_datetime(self.datetime.date_modified)
        return None

    @property
    def topics(self) -> List[str]:
        if self._topics_cache is None:
            self._topics_cache = normalize_list_str(self.section)
        return self._topics_cache or []

    @property
    def tags(self) -> List[str]:
        if self._tags_cache is None:
            if self.article and getattr(self.article, "tags", None):
                self._tags_cache = self.article.tags
            else:
                self._tags_cache = normalize_list_str(self.keywords) or normalize_list_str(self.news_keywords)
        return self._tags_cache or []

    @classmethod
    def to_meta_kwargs(cls) -> dict:
        kwargs = super().to_meta_kwargs()
        kwargs["article"] = OpenGraphArticle.to_meta_kwargs()
        kwargs["datetime"] = MetaDatetime.to_meta_kwargs()
        kwargs["geo"] = MetaGEO.to_meta_kwargs()
        kwargs["open_graph"] = OpenGraphMetadata.to_meta_kwargs()
        kwargs["twitter"] = TwitterCard.to_meta_kwargs()
        return kwargs

    @classmethod
    def from_soup(cls, soup: BeautifulSoup) -> "Meta":
        """
        Factory method to create a Meta instance from a BeautifulSoup object.
        It extracts metadata from <meta> tags.
        """
        meta_tags = soup.find_all("meta")
        meta_dict = {}
        for tag in meta_tags:
            key = tag.get("property") or tag.get("name")
            content = tag.get("content")
            if key and content:
                meta_dict[key] = content
        
        # Build nested objects
        article_data = {
            "published_time": meta_dict.get("article:published_time"),
            "modified_time": meta_dict.get("article:modified_time"),
            "author": meta_dict.get("article:author"),
            "section": meta_dict.get("article:section"),
            "tag": meta_dict.get("article:tag"),
        }
        article_data = {k: v for k, v in article_data.items() if v is not None}
        
        og_data = {
            "title": meta_dict.get("og:title"),
            "description": meta_dict.get("og:description"),
            "url": meta_dict.get("og:url"),
            "site_name": meta_dict.get("og:site_name"),
            "locale": meta_dict.get("og:locale"),
        }
        if meta_dict.get("og:image"):
            og_data["image"] = OpenGraphImage(image=meta_dict.get("og:image"))
        og_data = {k: v for k, v in og_data.items() if v is not None}
        
        twitter_data = {k.replace('twitter:', ''): v for k, v in meta_dict.items() if k.startswith('twitter:')}
        
        # This is a simplified mapping
        data = {
            "author": meta_dict.get("author"),
            "canonical": meta_dict.get("og:url") or meta_dict.get("canonical"),
            "description": meta_dict.get("description") or meta_dict.get("og:description"),
            "locale": meta_dict.get("og:locale"),
            "keywords": meta_dict.get("keywords"),
            "news_keywords": meta_dict.get("news_keywords"),
            "section": meta_dict.get("article:section"),
            "title": meta_dict.get("og:title") or meta_dict.get("twitter:title") or meta_dict.get("title"),
        }
        
        # Add nested objects if they have data
        if article_data:
            data["article"] = OpenGraphArticle.model_validate(article_data)
        if og_data:
            data["open_graph"] = OpenGraphMetadata.model_validate(og_data)
        if twitter_data:
            try:
                data["twitter"] = TwitterCard.model_validate(twitter_data)
            except ValidationError:
                pass
        
        # Clean up None values before validation
        validated_data = {k: v for k, v in data.items() if v is not None}
        
        try:
            return cls.model_validate(validated_data)
        except ValidationError as e:
            # In a real app, you'd log this error.
            print(f"Metadata validation error: {e}")
            return cls()


class ResponseMeta(BaseMeta):
    _rejected_topics = (
        "home",
        "homepage",
        "trang",
    )
    _rejected_tags = ()

    author: Optional[str] = None
    content: Optional[str] = None
    date_modified: Optional[datetime] = None
    date_published: Optional[datetime] = None
    description: Optional[str] = None
    geo: Optional[MetaGEO] = None
    main_points: List[str] = Field(default_factory=list)
    image: Optional[OpenGraphImage] = None
    language: Optional[str] = None
    locale: Optional[str] = None
    published_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    title: Optional[str] = None
    twitter_card: Optional[TwitterCard] = None
    canonical: Optional[HttpUrl] = None
    schema_org: Optional[Dict[str, Any]] = Field(default=None, description="Raw Schema.org JSON-LD data")

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

    @field_validator("author", "title", "description", mode="before")
    @classmethod
    def _strip_text(cls, v):
        return normalize_str(v)
    
    @classmethod
    def clean_main_points(cls, value: Union[str, List[str], None], *, max_length: int = None) -> List[str]:
        values = normalize_list_str(value)
        if max_length is not None:
            values = values[:max_length]
        return values

    @classmethod
    def clean_topics(cls, value: Any, *, max_length: int = 5) -> List[str]:
        return normalize_list_str(value, cls._rejected_topics)[:max_length]

    @classmethod
    def clean_tags(cls, value: Any, *, max_length: int = 10) -> List[str]:
        return normalize_list_str(value, cls._rejected_tags)[:max_length]

    @classmethod
    def from_soup(cls, soup: BeautifulSoup) -> "ResponseMeta":
        """
        Factory method to create a ResponseMeta instance from a BeautifulSoup object.
        It extracts metadata from <meta> tags.
        """
        from ..models.meta import Meta
        
        # Use Meta.from_soup to extract metadata
        meta = Meta.from_soup(soup)
        
        # Extract language from <html lang="..."> tag
        language = None
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            language = html_tag.get("lang")
        elif meta.locale:
            language = meta.locale.split('_')[0]  # Convert en_US to en
        
        # Convert to ResponseMeta
        return cls(
            author=meta.author,
            date_published=meta.date_published,
            date_modified=meta.date_modified,
            description=meta.description,
            image=meta.open_graph.image if meta.open_graph else None,
            language=language,
            locale=meta.locale,
            tags=meta.tags,
            topics=meta.topics,
            title=meta.title,
            canonical=meta.canonical,
        )


class Metadata(BaseModel):
    """
    Document-level metadata: title, url, authors, published date, lang, summary.
    """

    title: Optional[str] = Field(None, description="Human readable title")
    url: Optional[HttpUrl] = Field(None, description="Canonical URL")
    authors: List[str] = Field(default_factory=list)
    published: Optional[datetime] = Field(None, description="ISO datetime if available")
    lang: Optional[str] = Field(None, description="Language code, e.g. 'en'")
    summary: Optional[str] = Field(None, description="Short extracted summary")

    @field_validator("title", "summary", mode="before")
    @classmethod
    def _strip_text(cls, v):
        return normalize_str(v)

    @field_validator("url", mode="before")
    @classmethod
    def _normalize_url_field(cls, v):
        if v is None:
            return v
        return normalize_url(str(v))

