from __future__ import annotations

from datetime import datetime
from typing import Any, Union

from bs4 import BeautifulSoup, Tag
from pydantic import ConfigDict, model_validator

from ..utils import parse_datetime
from .base import AliasGenerator, Base

_SoupTag = Union[BeautifulSoup, Tag]


class _Sitemap(Base):
    model_config = ConfigDict(alias_generator=AliasGenerator.to_lower_case, extra="allow", arbitrary_types_allowed=True)

    @classmethod
    def from_string(cls, string: str) -> "BaseSitemap":
        return cls(_soup=cls.to_soup(string))

    @classmethod
    def to_soup(cls, soup: str) -> BeautifulSoup:
        if soup and isinstance(soup, str):
            soup = BeautifulSoup(soup, "xml")

        if isinstance(soup, (BeautifulSoup, Tag)):
            return soup

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="python")
        data.pop("soup", None)
        return data


class BaseSitemap(_Sitemap):
    soup: Union[_SoupTag, None] = None

    def is_valid(self) -> bool:
        if self.items:
            return True
        return False

    @classmethod
    def from_string(cls, string: str) -> "BaseSitemap":
        return cls(soup=cls.to_soup(string))

    @classmethod
    def tag_text(cls, soup: Union[_SoupTag, str]) -> Union[str, None]:
        if isinstance(soup, str):
            return soup

        if isinstance(soup, _SoupTag):
            return soup.text.strip()

    @classmethod
    def tag_datetime(cls, soup: Union[_SoupTag, str]) -> Union[datetime, None]:
        return parse_datetime(cls.tag_text(soup))


class SitemapGoogleNews(BaseSitemap):
    publication_date: Union[datetime, str, None] = None
    title: Union[str, None] = None

    @model_validator(mode="after")
    def set_attrs(self):
        if isinstance(self.soup, _SoupTag):
            self.title = self.tag_text(self.soup.find("title"))
            self.publication_date = self.tag_datetime(self.soup.find("publication_date"))
        return self


class SitemapItem(BaseSitemap):
    lastmod: Union[datetime, str, None] = None
    loc: Union[str, None] = None
    news: Union[SitemapGoogleNews, None] = None

    @model_validator(mode="after")
    def set_attrs(self):
        self.loc = self.tag_text(self.soup.find("loc"))
        self.lastmod = self.tag_datetime(self.soup.find("lastmod"))
        news_tag = self.soup.find("news")
        if not isinstance(news_tag, _SoupTag):
            news_tag = None

        self.news = SitemapGoogleNews(soup=news_tag)
        if not self.lastmod:
            if self.news.publication_date:
                self.lastmod = self.news.publication_date
        return self

    @classmethod
    def clean_lastmod(cls, obj):
        return parse_datetime(obj)

    def is_valid(self):
        if self.loc:
            return True
        return False

    def is_google_news(self) -> bool:
        if self.news:
            if self.news.title and self.news.publication_date:
                return True
        return False


class SitemapIndex(BaseSitemap):
    items: Union[list[SitemapItem], None] = []

    @model_validator(mode="after")
    def set_attrs(self):
        if isinstance(self.soup, _SoupTag):
            sitemap_tag = self.soup.find("sitemapindex")
            if not isinstance(sitemap_tag, _SoupTag):
                return self

            for tag in sitemap_tag.findAll("sitemap"):
                item = SitemapItem(soup=tag)
                if item and item.is_valid():
                    self.items.append(item)
        return self

    def is_google_news(self):
        if self.items:
            return self.items[0].is_google_news()
        return False


class SitemapURL(BaseSitemap):
    items: Union[list[SitemapItem], None] = []

    @model_validator(mode="after")
    def set_attrs(self):
        if isinstance(self.soup, _SoupTag):
            sitemap_tag = self.soup.find("urlset")
            if not isinstance(sitemap_tag, _SoupTag):
                return self

            for tag in sitemap_tag.findAll("url"):
                item = SitemapItem(soup=tag)
                if item and item.is_valid():
                    self.items.append(item)
        return self

    def is_google_news(self):
        if self.items:
            return self.items[0].is_google_news()
        return False
    
    