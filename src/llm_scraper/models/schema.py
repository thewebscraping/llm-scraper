from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Union, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator, ValidationError

from ..utils.normalization import normalize_datetime

__all__ = (
    "BaseSchema",
    "SchemaArticle",
    "SchemaNewsArticle",
    "SchemaAuthor",
    "SchemaImageObject",
    "SchemaOrganization",
    "SchemaPerson",
    "SchemaBreadcrumbItem",
    "SchemaBreadcrumbList",
    "SchemaWebPage",
    "SchemaWebSite",
    "SchemaJsonLD",
)

T = TypeVar("T", bound="BaseSchema")


class BaseSchema(BaseModel):
    """
    Base class for schema.org entities (Article, Person, Organization, ImageObject, etc.).
    Allows extra attributes (many JSON-LD nodes have extra keys).
    Validates expected _type / _context when subclass sets them.
    """

    _schema_type: Optional[Union[str, List[str]]] = None
    _schema_context: Optional[str] = None

    model_config = ConfigDict(alias_generator=None, extra="allow")

    @property
    def _id(self) -> Optional[str]:
        return self.model_extra.get("@id") or self.model_extra.get("_id")

    @property
    def _type(self) -> Optional[str]:
        return self.model_extra.get("@type") or self.model_extra.get("_type")

    @property
    def _context(self) -> Optional[str]:
        return self.model_extra.get("@context") or self.model_extra.get("_context")

    @model_validator(mode="after")
    def validate_schema(self) -> T:
        if self._schema_type is None:
            return self
        allowed = [self._schema_type] if isinstance(self._schema_type, str) else list(self._schema_type)
        t = self._type
        if t and t not in allowed:
            raise ValueError(f"Schema type mismatch: {t} not in {allowed}")
        if self._schema_context and self._context:
            if self._schema_context.lower() not in str(self._context).lower():
                raise ValueError(f"Schema context mismatch: {self._context} not contains {self._schema_context}")
        return self

    def to_json_ld(self) -> Dict[str, Any]:
        """
        Convert model to JSON-LD-like dict with @id/@type/@context and fields.
        """
        base: Dict[str, Any] = {}
        if self._id:
            base["@id"] = self._id
        if self._type:
            base["@type"] = self._type
        if self._context:
            base["@context"] = self._context

        for name, value in self.model_dump(mode="python").items():
            if name.startswith("_"):
                continue
            if isinstance(value, list):
                base[name] = [v.to_json_ld() if isinstance(v, BaseSchema) else v for v in value]
            elif isinstance(value, BaseSchema):
                base[name] = value.to_json_ld()
            else:
                base[name] = value
        return base

    def to_json_ld_str(self) -> str:
        return json.dumps(self.to_json_ld(), ensure_ascii=False, default=str, indent=2)


class BaseSchemaArticle(BaseSchema):
    isPartOf: Optional[Union[BaseSchema, Optional[str]]] = None
    author: Optional["SchemaAuthor"] = None
    headline: Optional[str] = None
    abstract: Optional[str] = None
    description: Optional[str] = None
    dateModified: Optional[Union[datetime, str]] = None
    datePublished: Optional[Union[datetime, str]] = None
    mainEntityOfPage: Optional[Union[BaseSchema, Optional[str]]] = None
    wordCount: Optional[int] = None
    commentCount: Optional[int] = None
    publisher: Optional[Union[BaseSchema, Optional[str]]] = None
    image: Optional[Union[BaseSchema, Optional[str]]] = None
    thumbnailUrl: Optional[str] = None
    keywords: Optional[Sequence[str]] = None
    articleSection: Optional[Sequence[str]] = None
    inLanguage: Optional[str] = None
    potentialAction: Optional[List[Any]] = None
    copyrightHolder: Optional[Union[BaseSchema, Optional[str]]] = None
    copyrightYear: Optional[Optional[str]] = None

    @property
    def topics(self) -> Optional[Sequence[str]]:
        """Expose articleSection as topics for compatibility."""
        return self.articleSection

    @model_validator(mode="after")
    def normalize_dates(self) -> "BaseSchemaArticle":
        if self.dateModified:
            self.dateModified = normalize_datetime(self.dateModified)
        if self.datePublished:
            self.datePublished = normalize_datetime(self.datePublished)
        return self


class Schema(BaseSchema):
    _schema_context = "schema.org"
    _graph: list[dict] | Any = None

    @property
    def graph(self) -> list[dict[str, Any]]:
        if self._graph is None:
            self._graph = self.model_extra.get("_graph", []) or []
            self._graph = [data for data in self._graph if isinstance(data, dict)]
        return self._graph


class SchemaAuthor(BaseSchema):
    _schema_type = ("Person", "Organization")
    name: Optional[str] = None
    url: Optional[str] = None


class SchemaNewsArticle(BaseSchemaArticle):
    _schema_type = "NewsArticle"


class SchemaArticle(BaseSchemaArticle):
    _schema_type = "Article"


class SchemaWebPage(BaseSchemaArticle):
    _schema_type = "WebPage"


class SchemaWebSite(BaseSchemaArticle):
    _schema_type = "WebSite"


class SchemaImageObject(BaseSchema):
    _schema_type = "ImageObject"
    inLanguage: Optional[str] = None
    url: Optional[str] = None
    contentUrl: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    caption: Optional[str] = None


class SchemaOrganization(BaseSchema):
    _schema_type = "Organization"
    name: Optional[str] = None
    url: Optional[str] = None
    alternateName: Optional[str] = None
    logo: Optional[SchemaImageObject] = None
    sameAs: Optional[List[str]] = None


class SchemaPerson(BaseSchema):
    _schema_type = "Person"
    name: Optional[str] = None
    image: Optional[SchemaImageObject] = None
    description: Optional[str] = None
    sameAs: Optional[List[str]] = None
    jobTitle: Optional[str] = None
    worksFor: Optional[Union[SchemaOrganization, str]] = None
    url: Optional[str] = None


class SchemaBreadcrumbItem(BaseSchema):
    _schema_type = "ListItem"
    name: Optional[str] = None
    position: Optional[int] = 0
    item: Optional[Union[SchemaPerson, SchemaOrganization, str]] = None

    @property
    def title(self) -> Optional[str]:
        if not self.name and isinstance(self.item, (SchemaPerson, SchemaOrganization)):
            return getattr(self.item, "name", None)
        return self.name


class SchemaBreadcrumbList(BaseSchema):
    _schema_type = "BreadcrumbList"
    itemListElement: List[SchemaBreadcrumbItem] = Field(default_factory=list)

    @property
    def topics(self) -> List[str]:
        topics: List[str] = []
        for it in self.itemListElement:
            t = it.title
            if t:
                topics.append(t)
        return list(dict.fromkeys(topics))[:5]


_TYPE_MAP: Mapping[str, type] = {
    "Article": SchemaArticle,
    "NewsArticle": SchemaNewsArticle,
    "ImageObject": SchemaImageObject,
    "Person": SchemaPerson,
    "Organization": SchemaOrganization,
    "BreadcrumbList": SchemaBreadcrumbList,
    "ListItem": SchemaBreadcrumbItem,
    "WebPage": SchemaWebPage,
    "WebSite": SchemaWebSite,
    "ListItemElement": SchemaBreadcrumbItem,
}


def _resolve_model_for_type(obj: Dict[str, Any]) -> Optional[BaseSchema]:
    t = obj.get("@type") or obj.get("_type")
    if isinstance(t, list):
        t = t[0] if t else None
    return _TYPE_MAP.get(t) if isinstance(t, str) else None


class SchemaJsonLD(BaseSchema):
    """
    Compatibility wrapper: parse raw JSON-LD (dict/string/list) into specific schema models
    when @type maps to a known class; otherwise keep raw content in `.raw`.
    Use: SchemaJsonLD.parse(json_ld)
    """

    raw: Any = None

    @classmethod
    def parse(cls, ld: Any) -> Union[T, List[T]]:
        if isinstance(ld, str):
            try:
                ld = json.loads(ld)
            except Exception:
                return cls(raw=ld)

        if isinstance(ld, list):
            out: List[T] = []
            for item in ld:
                parsed = cls.parse(item)
                out.append(parsed)
            return out

        if not isinstance(ld, dict):
            return cls(raw=ld)

        model_cls = _resolve_model_for_type(ld)
        if model_cls:
            try:
                return model_cls.model_validate(ld)
            except ValidationError:
                return cls(raw=ld)

        wrapper = cls(raw=ld)
        detected = ld.get("@type") or ld.get("_type")
        if detected:
            wrapper.model_extra["_detected_type"] = detected
        return wrapper
