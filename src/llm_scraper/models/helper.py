from __future__ import annotations

from datetime import datetime
from typing import Any, Union, Dict, List, Optional, Sequence, Type, TypeVar

from pydantic import ValidationError
from ..utils import normalize_soup, normalize_dict, normalize_list
from ..exceptions import ParserError
from .meta import (
    BaseMeta,
    MetaImage,
    ResponseMeta,
    TwitterCard,
    Meta,
    MetaDatetime,
    MetaGEO,
    OpenGraphMetadata,
)
from bs4 import Tag
from .schema import (
    BaseSchema,
    Schema,
    SchemaArticle,
    SchemaBreadcrumbList,
    SchemaImageObject,
    SchemaNewsArticle,
    SchemaOrganization,
    SchemaPerson,
    SchemaWebPage,
    SchemaWebSite,
    SchemaJsonLD as CompatSchemaJsonLD,
    BaseSchema as CompatBaseSchema,
)

__all__ = ("SchemaHelper",)

_TMeta = TypeVar("_TMeta", bound=BaseMeta)
_TSchema = TypeVar("_TSchema", bound=BaseSchema)

SchemaObject = (
    SchemaArticle
    | SchemaBreadcrumbList
    | SchemaImageObject
    | SchemaNewsArticle
    | SchemaOrganization
    | SchemaPerson
    | SchemaWebPage
    | SchemaWebSite
)
SchemaNodes = list[SchemaObject]
ScriptNodes = Union[
    str,
    list[str],
    tuple[str, ...],
    set[str],
    dict,
    list[dict],
    tuple[dict, ...],
    set[dict],
]


class BaseSchemaHelper:
    _NODE_CLASSES = (
        SchemaArticle,
        SchemaBreadcrumbList,
        SchemaImageObject,
        SchemaNewsArticle,
        SchemaOrganization,
        SchemaPerson,
        SchemaWebPage,
        SchemaWebSite,
    )

    _NAME_TO_PYDANTIC: Dict[str, type] = {
        "SchemaArticle": SchemaArticle,
        "SchemaBreadcrumbItem": SchemaBreadcrumbList,
        "SchemaBreadcrumbList": SchemaBreadcrumbList,
        "SchemaImageObject": SchemaImageObject,
        "SchemaNewsArticle": SchemaNewsArticle,
        "SchemaOrganization": SchemaOrganization,
        "SchemaPerson": SchemaPerson,
        "SchemaWebPage": SchemaWebPage,
        "SchemaWebSite": SchemaWebSite,
    }

    def __init__(self, scripts: list[str], *args, **kwargs):
        self._scripts = self.to_scripts(scripts)
        self._nodes: Optional[List[BaseSchema]] = None
        self._nodes_cache: Dict[str, BaseSchema] = {}
        self._schema = None
        self._breadcrumb = None
        self._news_article = None
        self._article = None
        self._image_object = None
        self._webpage = None
        self._website = None
        self._organization = None
        self._person = None

    @property
    def scripts(self) -> list[dict]:
        return self._scripts

    @property
    def nodes(self) -> SchemaNodes:
        if self._nodes is None:
            for script in self.scripts:
                obj = self.parse_obj(script)
                if isinstance(obj, Schema):
                    for graph in obj.graph:
                        parsed = self.parse_obj(graph)
                        if parsed:
                            self.set(parsed)
                else:
                    if obj:
                        self.set(obj)

            self._nodes = list(self._nodes_cache.values())

        return self._nodes

    @property
    def schema(self):
        return self.get(Schema.__name__)

    @property
    def news_article(self):
        return self.get(SchemaNewsArticle.__name__)

    @property
    def article(self):
        return self.get(SchemaArticle.__name__)

    @property
    def breadcrumb(self):
        return self.get(SchemaBreadcrumbList.__name__)

    @property
    def image(self):
        return self.get(SchemaImageObject.__name__)

    @property
    def webpage(self):
        return self.get(SchemaWebPage.__name__)

    @property
    def organization(self):
        return self.get(SchemaOrganization.__name__)

    @property
    def person(self):
        return self.get(SchemaPerson.__name__)

    @classmethod
    def parse_obj(cls, obj: Union[dict, str, bytes]) -> Optional[_TSchema]:
        """
        Robust parsing pipeline:
        1. Normalize script to dict using to_json.
        2. Try compatibility parser (SchemaJsonLD) which may return:
           - a compat BaseSchema instance,
           - a specific Schema* instance,
           - a wrapper with .raw, or a list.
        3. If compat returns a compat BaseSchema, convert to local pydantic model by name.
        4. Fallback to original per-model parse_obj attempts.
        """

        normalized = normalize_dict(obj) if isinstance(obj, (str, bytes, dict)) else obj

        try:
            parsed = CompatSchemaJsonLD.parse(obj)
        except Exception:
            parsed = None

        def _convert_compat_to_local(instance: Any) -> Optional[_TSchema]:
            if isinstance(instance, CompatBaseSchema):
                name = instance.__class__.__name__
                target = cls._NAME_TO_PYDANTIC.get(name)
                if target and issubclass(target, BaseSchema):
                    try:
                        return target.model_validate(instance.to_json_ld())
                    except Exception:
                        return None
                for model_class in cls._NODE_CLASSES:
                    if model_class.__name__.lower() in name.lower():
                        try:
                            return model_class.model_validate(instance.to_json_ld())
                        except Exception:
                            continue
            return None

        # if parsed is list, find first convertible node
        if isinstance(parsed, list):
            for p in parsed:
                conv = _convert_compat_to_local(p)
                if conv:
                    return conv
                # if parsing already returned a pydantic instance from compat, accept it
                if isinstance(p, tuple(cls._NODE_CLASSES)):  # type: ignore[misc]
                    return p

        # if parsed is one of the local pydantic classes already, return it
        if isinstance(parsed, tuple(cls._NODE_CLASSES)):  # type: ignore[misc]
            return parsed  # type: ignore[return-value]

        # if parsed is compat BaseSchema, try to convert
        if isinstance(parsed, CompatBaseSchema):
            conv = _convert_compat_to_local(parsed)
            if conv:
                return conv
            # fallback to raw dict from compat wrapper
            raw = parsed.raw if getattr(parsed, "raw", None) is not None else normalized
        else:
            # if compat returned wrapper or None, use normalized dict
            raw = normalized

        # Fallback: try existing model parsing as before
        for model_class in cls._NODE_CLASSES:
            try:
                node = model_class.model_validate(raw)
                if node:
                    return node
            except (ValidationError, ParserError):
                continue

        # final fallback: try top-level Schema (graph)
        try:
            node = Schema.model_validate(raw)
            if node and getattr(node, "graph", None):
                return node
        except (ValidationError, ParserError):
            pass

        return None

    @classmethod
    def to_scripts(cls, scripts: ScriptNodes) -> List[dict]:
        outputs = []
        for script in normalize_list(scripts):
            if isinstance(script, str):
                script_lower = str(script).lower()
                if "schema.org" in script_lower or "context" in script_lower:
                    script = normalize_dict(script)
            else:
                script = normalize_dict(script)
                
            if isinstance(script, dict):
                outputs.append(script)

        return outputs

    def set(self, obj: _TSchema):
        if isinstance(obj, tuple(self._NODE_CLASSES)):  # type: ignore[misc]
            self._nodes_cache[obj.__class__.__name__] = obj
            if isinstance(obj, Schema) and getattr(obj, "graph", None):
                self._nodes_cache[obj.__class__.__name__] = obj

    def get(self, key: str) -> Optional[_TSchema]:
        return self._nodes_cache.get(key)


class SchemaHelper(BaseSchemaHelper):
    """Schema Helper"""

    def to_response_meta(self) -> ResponseMeta:
        _ = self.nodes  # noqa

        title = self.get_title()
        topics = self.get_topics()
        if title:
            topics = [obj for obj in topics if obj not in title]

        return ResponseMeta(
            author=self.get_author(),
            topics=topics,
            date_modified=self.get_date_modified(),
            date_published=self.get_date_published(),
            image=self.get_image(),
            locale=self.get_locale(),
            title=title,
        )

    def get_author(self) -> Optional[str]:
        if self.news_article and self.news_article.author and self.news_article.author.name:
            return self.news_article.author.name

        if self.article and self.article.author and self.article.author.name:
            return self.article.author.name

        if self.person and self.person.name:
            return self.person.name

        return None

    def get_topics(self) -> List[str]:
        if self.news_article and getattr(self.news_article, "articleSection", None):
            return self.news_article.articleSection or []
        if self.article and getattr(self.article, "articleSection", None):
            return self.article.articleSection or []

        if self.breadcrumb and getattr(self.breadcrumb, "categories", None):
            return self.breadcrumb.categories or []

        return []

    def get_date_modified(self) -> Optional[datetime]:
        if self.news_article and self.news_article.dateModified:
            return self.news_article.dateModified
        if self.article and self.article.dateModified:
            return self.article.dateModified
        return None

    def get_date_published(self) -> Optional[datetime]:
        if self.news_article and getattr(self.news_article, "datePublished", None):
            return self.news_article.datePublished
        if self.article and getattr(self.article, "datePublished", None):
            return self.article.datePublished
        return None

    def get_image(self) -> Optional[MetaImage]:
        if self.news_article and getattr(self.news_article, "image", None):
            img = self.news_article.image
            url = getattr(img, "url", None)
            if url:
                return MetaImage(
                    url=url,
                    width=getattr(img, "width", None),
                    height=getattr(img, "height", None),
                )

        if self.article and getattr(self.article, "image", None):
            img = self.article.image
            url = getattr(img, "url", None)
            if url:
                return MetaImage(
                    url=url,
                    width=getattr(img, "width", None),
                    height=getattr(img, "height", None),
                )

        if self.news_article and getattr(self.news_article, "thumbnailUrl", None):
            return MetaImage(url=self.news_article.thumbnailUrl)

        if self.article and getattr(self.article, "thumbnailUrl", None):
            return MetaImage(url=self.article.thumbnailUrl)

        return None

    def get_locale(self) -> Optional[str]:
        if self.news_article and self.news_article.inLanguage:
            return self.news_article.inLanguage
        if self.article and self.article.inLanguage:
            return self.article.inLanguage
        return None

    def get_title(self) -> Optional[str]:
        if self.news_article and self.news_article.headline:
            return self.news_article.headline
        if self.article and self.article.headline:
            return self.article.headline
        return None


class MetaHelper:
    """Meta Helper"""

    _common_meta_attrs = (
        "name",
        "property",
        "itemprop",
    )
    _meta_canonical_attr = ("canonical",)

    def __init__(self, soup: Union[Tag, str, bytes], *args, **kwargs) -> None:
        self._soup = normalize_soup(soup)
        self._response = None
        self._canonical = None
        self._metas = None

    @property
    def soup(self) -> Tag:
        return self._soup

    @property
    def metas(self) -> List[Tag]:
        if self._metas is None:
            self._metas = self._get_meta_tags(self.soup)
        return self._metas

    @classmethod
    def _parse_str(
        cls,
        items: List[Tag],
        meta_values: Union[str, Sequence[str]],
        value_field: str = "content",
        is_object_list: bool = False,
    ) -> Union[str, List[str]]:
        if not isinstance(items, list):
            return ""

        outputs = []
        for item in items:
            if not isinstance(item, Tag):
                continue

            attrs = {str(k).lower(): v for k, v in item.attrs.items()}
            for key in cls._common_meta_attrs:
                meta_values_iter = meta_values if isinstance(meta_values, Sequence) else [meta_values]
                for value in meta_values_iter:
                    if not isinstance(value, str):
                        continue

                    meta_value = attrs.get(key)
                    if meta_value and str(meta_value).lower() == str(value).lower():
                        obj = item.attrs.get(value_field)
                        outputs.append(obj)

        if is_object_list:
            return outputs

        return outputs[0] if outputs else None

    @classmethod
    def _get_meta_str(
        cls,
        metas: List[Tag],
        meta_values: Union[str, Sequence[str]],
        is_object_list: bool = False,
    ) -> Union[str, List[str]]:
        return cls._parse_str(metas, meta_values, value_field="content", is_object_list=is_object_list)

    @classmethod
    def _get_meta_tags(cls, obj: Union[Tag, str, bytes]) -> List[Tag]:
        soup = normalize_soup(obj)
        if isinstance(soup, Tag):
            return [obj for obj in soup.find_all("meta") if isinstance(obj, Tag)]
        return []

    def get_title(self) -> Optional[str]:
        if self.soup:
            tag = self.soup.find("title")
            if tag:
                return tag.text.strip()

    def get_canonical(self) -> Optional[str]:
        if self.soup:
            tag = self.soup.find("link", attrs={"rel": "canonical"})
            if tag and tag.has_attr("href"):
                return tag["href"].strip()

    def get_meta_geo(self) -> Optional[MetaGEO]:
        return self.get_object(MetaGEO)

    def get_meta_open_graph(self) -> Optional[OpenGraphMetadata]:
        return self.get_object(OpenGraphMetadata)

    def get_twitter_card(self) -> Optional[TwitterCard]:
        return self.get_object(TwitterCard)

    def get_meta_datetime(self) -> Optional[MetaDatetime]:
        return self.get_object(MetaDatetime)

    def get_meta(self) -> Optional[Meta]:
        obj: Meta = self.get_object(Meta)
        if obj:
            obj.title = self.get_title()
            canonical = self.get_canonical()
            if canonical:
                obj.canonical = canonical
            return obj

    def get_kwargs(self, model_class: Type[_TMeta]) -> dict:
        def to_attr(obj):
            if isinstance(obj, dict):
                return {field: to_attr(attr) for field, attr in obj.items()}

            return self._get_meta_str(self.metas, obj)

        return {field: to_attr(attr) for field, attr in model_class.to_meta_kwargs().items()}

    def get_object(self, model_class: Type[_TMeta]) -> Optional[_TMeta]:
        try:
            obj = model_class.model_validate(self.get_kwargs(model_class))
            return obj
        except (ParserError, ValidationError):
            pass

    def get_response_meta(self) -> Optional[ResponseMeta]:
        obj = self.get_meta()
        if obj:
            return obj.to_response_meta()
