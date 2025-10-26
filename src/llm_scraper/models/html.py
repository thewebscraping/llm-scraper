from __future__ import annotations

import re
from dataclasses import dataclass, field
from hashlib import sha1
from html import unescape
from typing import Generator, Iterator, TypeVar
from urllib.parse import quote
from bs4 import Tag

_T = TypeVar("_T", bound="HTMLHelper")
HTMLTagAttr = list[tuple[str, re.Pattern[str]]] | tuple[tuple[str, re.Pattern[str]]]
HTMLTagGenerator = Generator
ReFlags = re.DOTALL | re.MULTILINE | re.IGNORECASE
# ... (rest of the constants are fine)
ReMatchIterator = Iterator[re.Match[str]]
ReMatchStr = re.Match[str] | None
RePatternStr = str | re.Pattern[str]
ReArray = list[tuple[re.Pattern, str]]
BreakTag = "<{break}>"
NodeTag = "<{node}>"
TabTag = "<{tab}>"
SPACE = " "
ASTERISK = "*"
DASH = "-"
UNDERSCORE = "_"
TILDE = "~"
SIGN = "#"
LEFT_ANGLE_BRACKET = ">"
COLON = ":"
GRAVE_ACCENT = "`"
VERTICAL_LINE = "|"

__all__ = (
    "ASTERISK",
    "A",
# ... (rest of __all__ is fine)
)


@dataclass(kw_only=True)
class Attr:
    name: str
    value: str


@dataclass(kw_only=True)
class HTMLHelper:
    tag: Tag
    processed_text: str = ""

    _md_prefix = ""
    _md_suffix = ""

    def __str__(self):
        return str(self.tag)

    @property
    def attrs(self) -> dict:
        return self.tag.attrs if self.tag else {}

    @property
    def text(self) -> str:
        return self.processed_text

    def to_markdown(self) -> str:
        """Converts the processed text to markdown using the class's prefix and suffix."""
        # The core logic simplifies greatly. The converter handles node traversal.
        # The helper's job is just to wrap the already-processed text from its children.
        if self.text is not None:
            return self._md_prefix + self.text.strip() + self._md_suffix
        return ""

    @classmethod
    def encode_tag(cls, text: str) -> str:
        text = text.replace("\n", BreakTag)
        return text.replace("\t", TabTag)

    @classmethod
    def decode_tag(cls, text: str) -> str:
        text = cls._replace_break(text)
        return cls._replace_tab(text)

    @staticmethod
    def _replace_break(text: str) -> str:
        return text.replace(BreakTag, "\n")

    @staticmethod
    def _replace_tab(text: str):
        return text.replace(TabTag, "\t")

    @staticmethod
    def urlsafe(url: str):
        scheme, *r = url.split("/")
        tags = [scheme]
        if r and len(r) > 1:
            tags.extend(r[:-1])
        else:
            if len(r) == 1:
                tags.append(quote(r[-1]))
        return "/".join(tags)


@dataclass(kw_only=True)
class NoEndHelper(HTMLHelper):
    # This class now behaves like a standard helper, as BeautifulSoup handles parsing.
    # The distinction is less critical but can be kept for logical grouping.
    pass


@dataclass(kw_only=True)
class Head(HTMLHelper):
    _tag_name = "head"

    def get_title(self) -> str:
        obj = HeadTitle.find(self.text)
        if obj:
            return obj.text

    def get_canonical(self) -> str:
        for obj in self.to_links():
            attrs_lower = {str(k).lower(): v for k, v in obj.attrs.items()}
            for _, value in attrs_lower.items():
                if value == "canonical":
                    return obj.attrs.get("href")

    def to_meta(self):
        return [obj for obj in HeadMeta.find_all(self.text)]

    def to_links(self):
        return [obj for obj in HeadLink.find_all(self.text)]


@dataclass(kw_only=True)
class HeadMeta(NoEndHelper):
    _re_pattern = r"(<meta\s(.*?)>)"
    _tag_name = "meta"


@dataclass(kw_only=True)
class HeadLink(NoEndHelper):
    _re_pattern = r"(<link\s(.*?)>)"
    _tag_name = "link"


@dataclass(kw_only=True)
class HeadTitle(HTMLHelper):
    _tag_name = "title"


@dataclass(kw_only=True)
class Body(HTMLHelper):
    _tag_name = "body"


@dataclass(kw_only=True)
class A(HTMLHelper):
    _tag_name = "a"

    def to_markdown(self):
        text = self.text.strip()
        if text:
            href = self.attrs.get("href")
            if href:
                not_startswith = ["javascript", "/", "#"]
                if not any(href.startswith(start) for start in not_startswith):
                    return f" [{text}]({href})"
            return text
        return ""


@dataclass(kw_only=True)
class Abbr(HTMLHelper):
    _tag_name = "abbr"


@dataclass(kw_only=True)
class Address(HTMLHelper):
    _tag_name = "address"


@dataclass(kw_only=True)
class Article(HTMLHelper):
    _tag_name = "article"


@dataclass(kw_only=True)
class Aside(HTMLHelper):
    _tag_name = "aside"


@dataclass(kw_only=True)
class Audio(HTMLHelper):
    _tag_name = "audio"


@dataclass(kw_only=True)
class Caption(HTMLHelper):
    _tag_name = "caption"


@dataclass(kw_only=True)
class Center(HTMLHelper):
    _tag_name = "center"

    def markdown(self):
        return "<center>" + self.text + "</center>"


@dataclass(kw_only=True)
class Code(HTMLHelper):
    _tag_name = "code"
    _md_prefix = BreakTag + GRAVE_ACCENT * 3
    _md_suffix = GRAVE_ACCENT * 3 + BreakTag


@dataclass(kw_only=True)
class DD(HTMLHelper):
    _tag_name = "del"
    _md_prefix = COLON + SPACE


@dataclass(kw_only=True)
class Del(HTMLHelper):
    _tag_name = "del"
    _md_prefix = TILDE
    _md_suffix = TILDE


@dataclass(kw_only=True)
class Details(HTMLHelper):
    _tag_name = "details"


@dataclass(kw_only=True)
class Div(HTMLHelper):
    _tag_name = "div"
    _md_prefix = BreakTag
    _md_suffix = BreakTag


@dataclass(kw_only=True)
class DL(HTMLHelper):
    _tag_name = "dl"


@dataclass(kw_only=True)
class DT(HTMLHelper):
    _tag_name = "dl"


@dataclass(kw_only=True)
class Embed(HTMLHelper):
    _tag_name = "embed"


@dataclass(kw_only=True)
class Figcaption(HTMLHelper):
    _tag_name = "figcaption"
    _md_prefix = BreakTag
    _md_suffix = BreakTag


@dataclass(kw_only=True)
class H1(HTMLHelper):
    _tag_name = "h1"
    _md_prefix = BreakTag + SIGN + SPACE
    _md_suffix = BreakTag


@dataclass(kw_only=True)
class H2(HTMLHelper):
    _tag_name = "h2"
    _md_prefix = BreakTag + SIGN * 2 + SPACE
    _md_suffix = BreakTag


@dataclass(kw_only=True)
class H3(HTMLHelper):
    _tag_name = "h3"
    _md_prefix = BreakTag + SIGN * 3 + SPACE
    _md_suffix = BreakTag


@dataclass(kw_only=True)
class H4(HTMLHelper):
    _tag_name = "h4"
    _md_prefix = BreakTag + SIGN * 4 + SPACE
    _md_suffix = BreakTag


@dataclass(kw_only=True)
class H5(HTMLHelper):
    _tag_name = "h5"
    _md_prefix = BreakTag + SIGN * 5 + SPACE
    _md_suffix = BreakTag


@dataclass(kw_only=True)
class H6(HTMLHelper):
    _tag_name = "h6"
    _md_prefix = BreakTag + SIGN * 6 + SPACE
    _md_suffix = BreakTag


@dataclass(kw_only=True)
class HR(HTMLHelper):
    _tag_name = "hr"
    _re_pattern = r"(<hr[^>]*?>)"
    _md_prefix = BreakTag + DASH * 3 + BreakTag


@dataclass(kw_only=True)
class Img(NoEndHelper):
    _tag_name = "img"
    _md_prefix = BreakTag * 2
    _md_suffix = BreakTag
    _safe_types: list = field(default_factory=lambda: [".webp", ".jpg", ".png", ".jpeg"])
    _lazy_css_attrs: list = field(default_factory=lambda: ["data-original", "data_original", "data-src", "srcset"])

    @property
    def src(self) -> str:
        src_val = self.attrs.get("src") or ""
        # Lowercase keys for consistent access
        attrs_lower = {k.lower().strip().replace("-", "_"): v for k, v in self.attrs.items()}

        if not str(src_val).startswith("http"):
            for lazy_attr in self._lazy_css_attrs:
                lazy_attr_key = lazy_attr.replace("-", "_").lower().strip()
                src_val = attrs_lower.get(lazy_attr_key)
                if src_val and str(src_val).startswith("http"):
                    break
        
        src_val = src_val or ""
        is_valid = False
        if str(src_val).startswith("http"):
            if any(ext in src_val.lower() for ext in self._safe_types):
                is_valid = True

        if is_valid:
            return unescape(src_val)
        return ""

    @property
    def title(self) -> str:
        return self._clean_dash(self.attrs.get("title") or "")

    @property
    def alt(self) -> str:
        return self._clean_dash(self.attrs.get("alt") or "")

    def to_markdown(self):
        markdown = self._md_prefix
        image_src = self.src
        if image_src:
            image_title = self.title
            image_alt = self.alt
            if image_title and image_alt:
                markdown += f'![{image_alt}]({image_src} "{image_title}")'
            elif image_alt:
                markdown += f'![{image_alt}]({image_src})'
            else:
                markdown += f"![]({image_src})"

            markdown += self._md_suffix
        return markdown

    def _clean_dash(self, string: str):
        return re.sub(r" +", " ", string.replace("-", " - ").strip())


@dataclass(kw_only=True)
class Main(HTMLHelper):
    _tag_name = "main"


@dataclass(kw_only=True)
class Menu(HTMLHelper):
    _tag_name = "menu"


@dataclass(kw_only=True)
class Mark(HTMLHelper):
    _tag_name = "mark"


@dataclass(kw_only=True)
class Nav(HTMLHelper):
    _tag_name = "nav"


@dataclass(kw_only=True)
class P(HTMLHelper):
    _tag_name = "p"
    _md_prefix: str = BreakTag * 2
    _md_suffix: str = BreakTag * 2


@dataclass(kw_only=True)
class Pre(HTMLHelper):
    _tag_name = "pre"
    _md_prefix = GRAVE_ACCENT * 3
    _md_suffix = GRAVE_ACCENT * 3


@dataclass(kw_only=True)
class Option(HTMLHelper):
    _tag_name = "option"


@dataclass(kw_only=True)
class S(HTMLHelper):
    _tag_name = "s"
    _md_prefix = TILDE * 2
    _md_suffix = TILDE * 2


@dataclass(kw_only=True)
class Section(HTMLHelper):
    _tag_name = "section"


@dataclass(kw_only=True)
class Select(HTMLHelper):
    _tag_name = "select"


@dataclass(kw_only=True)
class Space(HTMLHelper):
    _md_prefix = SPACE
    _md_suffix = SPACE


@dataclass(kw_only=True)
class Small(HTMLHelper):
    _tag_name = "small"


@dataclass(kw_only=True)
class Span(HTMLHelper):
    _tag_name = "span"
    _md_prefix = SPACE
    _md_suffix = SPACE


@dataclass(kw_only=True)
class Ins(HTMLHelper):
    _tag_name = "ins"
    _md_prefix = "<ins>"
    _md_suffix = "</ins>"


@dataclass(kw_only=True)
class Cite(HTMLHelper):
    _tag_name = "cite"
    _md_prefix = SPACE + UNDERSCORE
    _md_suffix = UNDERSCORE + SPACE


@dataclass(kw_only=True)
class Strong(HTMLHelper):
    _tag_name = "strong"
    _md_prefix = SPACE + ASTERISK * 2
    _md_suffix = ASTERISK * 2 + SPACE
    _children_nodes: list = field(default=(Span,))

    def clean_children_nodes(self, markdown: str, is_striped: bool = True) -> str:
        return super().clean_children_nodes(markdown, is_striped)


@dataclass(kw_only=True)
class Em(HTMLHelper):
    _tag_name = "em"
    _md_prefix = SPACE + UNDERSCORE
    _md_suffix = UNDERSCORE + SPACE
    _children_nodes: list = field(
        default=(
            Span,
            Strong,
            Small,
        )
    )

    def clean_children_nodes(self, markdown: str, is_striped: bool = True) -> str:
        return super().clean_children_nodes(markdown, is_striped)


@dataclass(kw_only=True)
class Italic(HTMLHelper):
    _tag_name = "i"
    _md_prefix = SPACE + UNDERSCORE
    _md_suffix = UNDERSCORE + SPACE


@dataclass(kw_only=True)
class Strike(Space):
    _tag_name = "strike"
    _md_prefix = TILDE
    _md_suffix = TILDE


@dataclass(kw_only=True)
class BTag(HTMLHelper):
    _tag_name = "b"
    _md_prefix = SPACE + ASTERISK * 2
    _md_suffix = ASTERISK * 2 + SPACE


@dataclass(kw_only=True)
class U(HTMLHelper):
    _tag_name = "u"


@dataclass(kw_only=True)
class Sub(HTMLHelper):
    _tag_name = "sub"


@dataclass(kw_only=True)
class Summary(HTMLHelper):
    _tag_name = "summary"


@dataclass(kw_only=True)
class Sup(HTMLHelper):
    _tag_name = "sup"


@dataclass(kw_only=True)
class SVG(HTMLHelper):
    _tag_name = "svg"


@dataclass(kw_only=True)
class TH(HTMLHelper):
    _tag_name = "th"
    _md_prefix = SPACE
    _md_suffix = SPACE + VERTICAL_LINE


@dataclass(kw_only=True)
class TD(HTMLHelper):
    _tag_name = "td"
    _md_prefix = SPACE
    _md_suffix = SPACE + VERTICAL_LINE

    def clean_children_nodes(self, markdown: str, is_striped: bool = True) -> str:
        return super(TD, self).clean_nested_nodes(markdown, is_striped)


@dataclass(kw_only=True)
class ColGroup(HTMLHelper):
    _tag_name = "colgroup"


@dataclass(kw_only=True)
class TR(HTMLHelper):
    _tag_name = "tr"
    _md_prefix = BreakTag + VERTICAL_LINE + SPACE
    _md_suffix = ""
    _children_nodes: list = field(default=(TD,))

    def clean_children_nodes(self, markdown: str, is_striped: bool = True) -> str:
        return super(TR, self).clean_nested_nodes(markdown, is_striped)


@dataclass(kw_only=True)
class THead(HTMLHelper):
    _tag_name = "thead"
    _md_prefix = BreakTag
    _md_suffix = ""
    _children_nodes: list = field(default=(TR,))

    def clean_children_nodes(self, markdown: str, is_striped: bool = True) -> str:
        return super(THead, self).clean_nested_nodes(markdown, is_striped)


@dataclass(kw_only=True)
class TBody(HTMLHelper):
    _tag_name = "tbody"
    _md_prefix = ""
    _md_suffix = BreakTag * 2
    _children_nodes: list = field(default=(TR,))

    def markdown(self) -> str:
        markdown = self.decode_tag(self.text).strip()
        if markdown:
            markdown += self._md_suffix
            return markdown

    def clean_children_nodes(self, markdown: str, is_striped: bool = True) -> str:
        return super(TBody, self).clean_nested_nodes(markdown, is_striped)


@dataclass(kw_only=True)
class TFoot(HTMLHelper):
    _tag_name = "tfoot"


@dataclass(kw_only=True)
class Table(HTMLHelper):
    _tag_name = "table"
    _md_prefix = BreakTag
    _md_suffix = BreakTag

    def to_markdown(self) -> str:
        # The new converter processes children first, so self.text contains
        # the already-converted markdown of the table's contents (thead, tbody, etc.).
        # The Table helper's job is now to wrap it correctly.
        # A more advanced implementation would re-parse the child markdown to format columns,
        # but for now, we'll just wrap the processed content.
        
        # A simple approach: just return the processed children, wrapped in newlines.
        return self._md_prefix + self.text.strip() + self._md_suffix



@dataclass(kw_only=True)
class Time(HTMLHelper):
    _tag_name = "time"


@dataclass(kw_only=True)
class OL(HTMLHelper):
    _tag_name = "ol"
    _md_suffix = BreakTag * 2


@dataclass(kw_only=True)
class UL(HTMLHelper):
    _tag_name = "ul"
    _md_prefix = BreakTag
    _md_suffix = BreakTag * 2


@dataclass(kw_only=True)
class LI(HTMLHelper):
    _tag_name = "li"
    _md_prefix = DASH + SPACE
    _md_suffix = BreakTag

    def to_markdown(self) -> str:
        md = super().to_markdown()
        md = re.sub(r"^-\s+(%s)+\s+" % BreakTag, "- ", md).strip()
        return md


@dataclass(kw_only=True)
class VAR(HTMLHelper):
    _tag_name = "var"


@dataclass(kw_only=True)
class Video(HTMLHelper):
    _tag_name = "video"


@dataclass(kw_only=True)
class Picture(HTMLHelper):
    _tag_name = "picture"
    _md_prefix = BreakTag * 2
    _md_suffix = BreakTag * 2

    def markdown(self) -> str:
        markdown = self._md_prefix
        img = Img.find(self.text)
        if img:
            markdown += img.decode_tag(img.markdown()).strip()
            markdown += self._md_suffix
        return markdown


@dataclass(kw_only=True)
class Source(NoEndHelper):
    _tag_name = "source"
    _re_tag = r"(<source[^>]*?>)"

    def markdown(self) -> str:
        markdown = self._md_prefix
        img = Img.find(self.text)
        if img:
            markdown += img.decode_tag(img.markdown()).strip()
            markdown += self._md_suffix
        return markdown


@dataclass(kw_only=True)
class Figure(HTMLHelper):
    _tag_name = "figure"
    _md_prefix = BreakTag * 2
    _md_suffix = BreakTag * 2
    _children_nodes: list = field(
        default=(
            Img,
            Figcaption,
        )
    )

    def markdown(self) -> str:
        markdown = self._md_prefix
        img = Img.find(self.text)
        figcaption = Figcaption.find(self.text)
        if img:
            if figcaption:
                markdown += img.decode_tag(img.markdown()).strip()
                markdown += BreakTag
                markdown += figcaption.decode_tag(figcaption.markdown()).strip()
            else:
                markdown += img.markdown()
            markdown += self._md_suffix
        return markdown


@dataclass(kw_only=True)
class Blockquote(HTMLHelper):
    _tag_name = "blockquote"
    _md_prefix = BreakTag + LEFT_ANGLE_BRACKET + SPACE
    _md_suffix = ""
    _children_nodes: list = field(
        default=(
            P,
            Div,
        )
    )

    def clean_children_nodes(self, markdown: str, is_striped: bool = True) -> str:
        return super(Blockquote, self).clean_nested_nodes(markdown, is_striped)

    def markdown(self) -> str:
        return self.encode_tag(self.to_markdown())


@dataclass(kw_only=True)
class BR(NoEndHelper):
    _tag_name = "br"
    _md_prefix = BreakTag

    def to_markdown(self) -> str:
        return self._md_prefix


@dataclass(kw_only=True)
class Script(HTMLHelper):
    _tag_name = "script"

    def to_markdown(self) -> str:
        """Text/HTML to Markdown"""
        return ""


@dataclass(kw_only=True)
class NoScript(HTMLHelper):
    _tag_name = "noscript"

    def to_markdown(self) -> str:
        """Text/HTML to Markdown"""
        return ""


@dataclass(kw_only=True)
class IFrame(HTMLHelper):
    _tag_name = "iframe"

    def to_markdown(self) -> str:
        """Text/HTML to Markdown"""
        return ""


@dataclass(kw_only=True)
class Button(HTMLHelper):
    _tag_name = "button"


@dataclass(kw_only=True)
class Label(HTMLHelper):
    _tag_name = "label"


@dataclass(kw_only=True)
class TextArea(HTMLHelper):
    _tag_name = "textarea"


@dataclass(kw_only=True)
class Input(NoEndHelper):
    _tag_name = "input"
    _re_pattern = r"(<input[^>]*?>)"


@dataclass(kw_only=True)
class Form(HTMLHelper):
    _tag_name = "form"


HEADER_TAGS = (H1, H2, H3, H4, H5, H6)

MAIN_TAGS = (
    Article,
    Main,
    Section,
    Div,
)

EMPHASIS_TAGS = (
    Italic,
    Em,
    Cite,
    Strong,
    Ins,
    BTag,
)

UNUSED_TAGS = (
    Script,
    NoScript,
    IFrame,
    Form,
    Button,
    Label,
    TextArea,
    Input,
    SVG,
    HR,
    Nav,
    Time,
)

IMAGE_TAGS = (
    Figure,
    Picture,
    Source,
    Img,
)

LINK_TAGS = (A,)

BULLET_TAGS = (
    LI,
    OL,
    UL,
)

PARAGRAPH_TAGS = (
    P,
    Span,
)

TABLE_TAGS = (Table,)

CODE_TAGS = (Code,)

BLOCKQUOTE_TAGS = (Blockquote,)

BREAK_TAGS = (BR,)
