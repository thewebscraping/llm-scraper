from __future__ import annotations

import re
import json
from datetime import datetime
from typing import List, Optional, Union, Sequence
from urllib.parse import urlparse, urlunparse
from bs4 import Tag, BeautifulSoup

ISO_DATETIME_PATTERNS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def normalize_soup(markup: Union[Tag, str, bytes], features: str = "lxml") -> Tag:
    if isinstance(markup, Tag):
        return markup

    if isinstance(markup, bytes):
        markup = markup.decode("utf-8", errors="ignore")
    return BeautifulSoup(markup, features)


def normalize_url(u: str) -> str:
    try:
        p = urlparse(u.strip())
        if not p.scheme:
            p = p._replace(scheme="https")
        return urlunparse(p)
    except Exception:
        return u.strip()


def normalize_datetime(value: Union[str, datetime, None]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ISO_DATETIME_PATTERNS:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def normalize_list(value) -> List:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]

def normalize_list_str(value: Optional[str], rejected_keywords: Sequence[str] = (), *args, **kwargs) -> List[str]:
    values = []
    if isinstance(value, (list, tuple, set)):
        values = [normalize_str(s) for s in value if isinstance(s, str)]
    else:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="ignore")
        if isinstance(value, str):
            values = [normalize_str(s) for s in re.split(r"[\r\n\t,]+", value)]
    return [s.strip() for s in values if s.strip() and s.lower().strip() not in rejected_keywords]


def normalize_str(value: Optional[Union[str, bytes]], *args, **kwargs) -> Optional[str]:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if not isinstance(value, str) or not value:
        return ""
    s = re.sub(r"[\r\n\t]+", " ", value)
    s = re.sub(r" {2,}", " ", value)
    return s.strip()

def normalize_dict(obj: Union[dict, str, bytes]) -> dict:
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, bytes):
        obj = obj.decode("utf-8")
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            pass
    return {}
