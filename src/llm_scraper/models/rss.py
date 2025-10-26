from __future__ import annotations

import re
from copy import copy
from datetime import datetime
from html import unescape
from typing import Any, Union, Sequence, List, Self, TypeVar, ClassVar, Optional

from bs4 import BeautifulSoup, Tag
from pydantic import ConfigDict, Field, model_validator

from ..utils import normalize_datetime, normalize_list_str
from .base import AliasGenerator, BaseModel


T = TypeVar("T", bound="BaseRSS")

class BaseRSS(BaseModel):
    # class-level configuration (not model fields)
    _excluded_fields: ClassVar[List[str]] = []
    _priority_fields: ClassVar[List[str]] = []
    _find_all_fields: ClassVar[List[str]] = []

    model_config = ConfigDict(alias_generator=AliasGenerator.to_camel_case, extra="allow", arbitrary_types_allowed=True)
    soup: Optional[Union[Tag, list[Tag]]] = None

    def to_dict(self):
        data = super().to_dict()
        data.pop("soup", None)
        return data

    @classmethod
    def find(cls, soup: Union[Tag, str], field: str) -> Union[Tag, None]:
        soup = cls.to_soup(soup)
        if soup:
            tag = soup.find(re.compile(field, re.MULTILINE | re.IGNORECASE))
            if isinstance(tag, Tag):
                return tag

    @classmethod
    def find_all(cls, soup: Union[Tag, str], field: str) -> List[Tag]:
        soup = cls.to_soup(soup)
        if soup:
            return [
                obj for obj in soup.find_all(re.compile(field, re.MULTILINE | re.IGNORECASE)) if isinstance(obj, Tag)
            ]
        return []

    @classmethod
    def from_string(cls, string: str) -> T:
        return cls(soup=cls.to_soup(string))

    @classmethod
    def tag_text(cls, tag: Union[str, Tag, BeautifulSoup]) -> str:
        if isinstance(tag, str):
            text = tag.strip()
        elif isinstance(tag, Tag) or isinstance(tag, BeautifulSoup):
            # Tag and BeautifulSoup share .get_text / .text
            try:
                text = tag.get_text(strip=True)
            except Exception:
                text = str(tag).strip()
        else:
            text = ""
        return cls.clean_string(text)

    @classmethod
    def to_soup(cls, obj: Union[str, Tag]) -> Tag:
        if obj and isinstance(obj, str):
            obj = BeautifulSoup(unescape(obj), "xml")

        if isinstance(obj, (BeautifulSoup, Tag)):
            return obj


class RSSImage(BaseRSS):
    height: Union[str, int, float, None] = None
    title: Union[str, None] = None
    type: Union[str, None] = None
    url: Union[str, None] = None
    width: Union[str, int, float, None] = None

    def to_number(self, obj):
        try:
            return int(obj)
        except (ValueError, TypeError):
            try:
                return int(float(obj))
            except Exception:
                return None

    @model_validator(mode="after")
    def set_attrs(self):
        attrs = {}
        media = self.find(self.soup, "content")
        if media:
            attrs = media.attrs.copy()
        else:
            tag = self.find(self.soup, "description")
            if tag:
                image_tag = self.find(tag.string, "img")
                if image_tag:
                    attrs = image_tag.attrs.copy()
                    attrs.update(dict(url=attrs.get("src"), soup=image_tag))

        for k, v in attrs.items():
            if not v:
                continue

            if hasattr(self, k):
                setattr(self, k, v)

        if self.height:
            self.height = self.to_number(self.height)

        if self.width:
            self.width = self.to_number(self.width)

        if self.url and not self.type:
            self.set_image_type()

        return self

    def set_image_type(self):
        url_lower = str(self.url).lower()
        if ".webp" in url_lower:
            self.type = "image/webp"
        elif ".png" in url_lower:
            self.type = "image/png"
        elif ".jpg" in url_lower:
            self.type = "image/jpeg"
        elif ".jpeg" in url_lower:
            self.type = "image/jpeg"

    def to_dict(self):
        if self.url:
            return dict(url=self.url, type=self.type, height=self.height, width=self.width, alt=self.title)
        return {}


class CommonRSS(BaseRSS):
    description: Union[str, None] = None
    image: Union[RSSImage, None] = None
    link: Union[str, None] = None
    title: Union[str, None] = None

    @model_validator(mode="after")
    def set_common_attrs(self):
        self.title = self.tag_text(self.find(self.soup, "title"))
        self.link = self.tag_text(self.find(self.soup, "link"))
        description_tag = self.find(self.soup, "description")
        if description_tag:
            for tag in description_tag.find_all("p"):
                if tag.find("a"):
                    continue

                self.description = self.tag_text(tag)
                break

        self.image = RSSImage(soup=self.soup)
        if not self.image.title:
            self.image.title = self.title

        return self


class RSSItem(CommonRSS, BaseRSS):
    _priority_fields: ClassVar[Sequence[str]] = ["categories", "tags", "creator"]

    pubDate: Union[datetime, str, None] = None
    guid: Union[str, None] = None
    creator: Union[str, None] = None
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def set_item_attrs(self):
        self.pubDate = normalize_datetime(self.tag_text(self.find(self.soup, "pubDate")))
        self.guid = self.tag_text(self.find(self.soup, "guid"))
        self.creator = self.tag_text(self.find(self.soup, "creator"))

        for tag in self.find_all(self.soup, "category"):
            categories = normalize_list_str(self.tag_text(tag))
            self.categories.extend(categories)

        for tag in self.find_all(self.soup, "keywords"):
            keywords = normalize_list_str(self.tag_text(tag))
            self.tags.extend(keywords)

        return self

    def is_valid(self) -> bool:
        if self.title and self.link and isinstance(self.pubDate, datetime):
            return True
        return False


class RSSChannel(CommonRSS, BaseRSS):
    _priority_fields: ClassVar[Sequence[str]] = ["items"]

    items: List[RSSItem] = Field(default_factory=list)

    @property
    def atom(self) -> Union[str, None]:
        tag = self.soup.find("atom:link")
        if tag:
            return tag.attrs.get("href")


class RSS(BaseRSS):
    _excluded_fields: ClassVar[Sequence[str]] = ("channel",)
    channel: Optional[RSSChannel] = None

    @classmethod
    def from_string(cls, string: Union[Tag, str], **kwargs) -> "BaseRSS":
        soup = cls.to_soup(string)
        if soup:
            rss_tag = soup.find("rss")
            if rss_tag:
                soup = rss_tag

            items = []
            for tag in cls.find_all(soup, "item"):
                item_obj = RSSItem(soup=copy(tag))
                if item_obj.is_valid():
                    items.append(item_obj)

                tag.decompose()

            return cls(soup=soup, channel=RSSChannel(soup=soup, items=items))

        return cls(channel=None)

    @property
    def version(self):
        if self.soup:
            return self.soup.attrs.get("version")

    @property
    def atom(self):
        if self.soup:
            return self.soup.attrs.get("xmlns:atom")

    def is_valid(self) -> bool:
        if self.channel:
            if self.channel.items:
                return True
        return False