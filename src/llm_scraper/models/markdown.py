from __future__ import annotations

import re
from html import unescape
from unicodedata import normalize

from .html import (
    BLOCKQUOTE_TAGS,
    BREAK_TAGS,
    BULLET_TAGS,
    CODE_TAGS,
    EMPHASIS_TAGS,
    HEADER_TAGS,
    IMAGE_TAGS,
    LINK_TAGS,
    MAIN_TAGS,
    PARAGRAPH_TAGS,
    TABLE_TAGS,
    UNUSED_TAGS,
    Body,
    BreakTag,
    HTMLCache,
    HTMLHelper,
    ReArray,
)


class MarkdownHelper:
    accepted_tags = []
    excluded_tags = ["header", "footer", "style", "meta"]
    header_tags = HEADER_TAGS
    main_tags = MAIN_TAGS
    emphasis_tags = EMPHASIS_TAGS
    unused_tags = UNUSED_TAGS
    image_tags = IMAGE_TAGS
    link_tags = LINK_TAGS
    bullet_tags = BULLET_TAGS
    paragraph_tags = PARAGRAPH_TAGS
    table_tags = TABLE_TAGS
    code_tags = CODE_TAGS
    blockquote_tags = BLOCKQUOTE_TAGS
    break_tags = BREAK_TAGS

    _re_sub_html_space_patterns = [
        (re.compile(r"\s+"), " "),
        (re.compile(r"(?i)>\s+<"), "><"),
    ]
    _re_sub_unicode_space_patterns = [
        (re.compile("\u200b"), " "),
        (re.compile("\xa0"), " "),
    ]
    _re_sub_punctuation_patterns = [
        (r"===+", "\n"),
        (r"[“”‘’]", '"'),
        (r"–", "-"),
        (r"(?!^-) +-", " - "),
        (r"(?!^-)- +", " - "),
        (r":+", ":"),
        (r"!+", "!"),
        (r"\?+", "?"),
        (r",+", ","),
        (r";+", ";"),
        (r"\.\.+", "..."),
        (r"\. \(\.\.\.\)", "..."),
        (r"(\- +\- +\- +)+", "---"),  # Table head
        (r" +", " "),
        (r" +([!?:;,.])", r"\1"),
        (r"[!?:;,]\.", "."),
    ]
    _re_sub_emphasis_patterns = [
        (r"\*\*(.*?)\*\*", r"\1"),
        (r"__(.*?)__", r"\1"),
        (r"_(.*?)_", r"\1"),
    ]
    _re_sub_emphasis_start_pattern = r"^[?!.,]+"
    _re_sub_comment_pattern = r"(?=<!--)([\s\S]*?)-->"

    def __init__(self, string: str, *, remove_image: bool = False, remove_link: bool = True, **kwargs):
        self.string = string
        self.caches = {}
        self.remove_link = remove_link
        self.remove_image = remove_image

    def format(self) -> str:
        self._preprocess()
        self.unused()
        self.codes()
        self.space()
        self.main()
        self.headers()
        self.blockquotes()
        self.emphasis()
        self.images()
        self.paragraphs()
        self.links()
        self.bullets()
        self.tables()
        self._postprocess()
        return unescape(self.string)

    def _preprocess(self):
        self.string = self.unicode(self.string)
        self.string = self.normalize(self.string)
        self.string = self.clean_space(self.string)

    def _postprocess(self):
        self.string = re.sub(r"<[^>]*>", BreakTag, self.string)
        for break_tag in self.break_tags:
            self.string = break_tag.encode_break_tag(self.string)

        self.string = re.sub(r"\*\*\*+", " ", self.string)
        for cache_id, cache_obj in self.caches.items():
            self.string = self.string.replace(cache_id, cache_obj.tag_class.markdown())

        self.string = HTMLHelper.decode_tag(self.string)
        self.string = self.capitalize(self.string)
        self.string = self.clean_bracket(self.string)
        sentences = []
        self.string = re.sub(r"\n\n+", "\n\n", HTMLHelper.decode_tag(self.string).strip()).strip()
        for sentence in self.string.split("\n"):
            sentence = self.clean_punctuation(sentence)
            sentence = "" if len(sentence) <= 1 else sentence
            sentences.append(sentence)

        if self.remove_image:
            self.string = self.delete_link(self.string)

        if self.remove_link:
            self.string = self.delete_image(self.string)

        self.string = "\n".join([s.strip() for s in sentences])

    @staticmethod
    def _replace_re(text: str, patterns: ReArray) -> str:
        for pattern in patterns:
            text = re.sub(pattern[0], pattern[1], text).strip()
        return text

    def _replace_markdown(self, klass: type[[HTMLHelper]]):
        objs = klass.find_all(self.string)
        for obj in objs:
            self.string = self.string.replace(obj.string, obj.markdown())

    def images(self):
        for klass in self.image_tags:
            self._replace_markdown(klass)

    def links(self):
        for klass in self.link_tags:
            self._replace_markdown(klass)

    def emphasis(self):
        for klass in self.emphasis_tags:
            self._replace_markdown(klass)

    def blockquotes(self):
        for klass in self.blockquote_tags:
            self._replace_markdown(klass)

    def bullets(self):
        for klass in self.bullet_tags:
            self._replace_markdown(klass)

    def paragraphs(self):
        for klass in self.paragraph_tags:
            self._replace_markdown(klass)

    def tables(self):
        for klass in self.table_tags:
            self._replace_markdown(klass)

    def codes(self):
        for klass in self.code_tags:
            objs = klass.find_all(self.string)
            for obj in objs:
                cache_obj = HTMLCache.from_str(obj.string, obj)
                self.string = self.string.replace(obj.string, cache_obj.id)
                self.caches[cache_obj.id] = cache_obj

    def headers(self):
        for klass in self.header_tags:
            self._replace_markdown(klass)

    @staticmethod
    def capitalize(string: str):
        def _capfirst(match):
            if isinstance(match, re.Match):
                return match.group().title()
            return match

        if isinstance(string, str):
            return re.sub(r"([!.?] [a-z])", _capfirst, string)

        return string

    def space(self):
        self.string = self._replace_re(self.string, self._re_sub_unicode_space_patterns)
        self.string = self._replace_re(self.string, self._re_sub_html_space_patterns)

    def main(self):
        for klass in self.main_tags:
            self._replace_markdown(klass)

    def unused_links(self):
        self.string = re.sub(r"(?<!!)\[(\s+|)]\(.*?\)", "", self.string)  # remove links without text

    def unused(self):
        self.comments()
        body = Body.find(self.string)
        if body:
            self.string = body.text
        for klass in self.unused_tags:
            objs = klass.find_all(self.string)
            for obj in objs:
                self.string = self.string.replace(obj.string, "")

        for excluded_tag in set(self.excluded_tags):
            objs = HTMLHelper.find_all(self.string, tag_name=excluded_tag)
            for obj in objs:
                self.string = self.string.replace(obj.string, "")

    def comments(self):
        self.string = re.sub(self._re_sub_comment_pattern, "", self.string)

    @classmethod
    def from_string(cls, string: str | bytes, **options):
        if isinstance(string, bytes):
            string = string.decode("utf-8")

        string = re.sub(r"\s+", " ", string).strip()
        return cls(string=string, **options)

    @classmethod
    def clean_string(
        cls,
        string: str | bytes,
        *,
        remove_image: bool = False,
        remove_link: bool = True,
        clean_punctuation: bool = True,
        clean_bracket: bool = True,
        clean_emphasis: bool = True,
    ) -> str:
        string = cls.clean_nested_ul(string)
        wraps = [cls.unicode, cls.unescape, cls.normalize, cls.clean_space]
        if remove_image:
            wraps.append(cls.delete_image)

        if remove_link:
            wraps.append(cls.delete_link)
        if clean_emphasis:
            wraps.append(cls.clean_emphasis)

        if clean_bracket:
            wraps.append(cls.clean_bracket)

        if clean_punctuation:
            wraps.append(cls.clean_punctuation)

        for wrap_fn in wraps:
            string = wrap_fn(string)

        return str(string).strip()

    @classmethod
    def unicode(cls, string: str | bytes) -> str:
        if isinstance(string, bytes):
            return string.decode("utf-8")
        if isinstance(string, str):
            return string.encode("utf-8").decode("utf-8")
        return ""

    @staticmethod
    def unescape(string: str) -> str:
        return unescape(string)

    @staticmethod
    def normalize(string: str) -> str:
        return normalize("NFKC", string.encode("utf-8").decode("utf-8"))

    @staticmethod
    def clean_bracket(string: str):
        string = re.sub(re.compile(r"\( +", re.M), "(", string)
        string = re.sub(re.compile(r" +\)", re.M), ")", string)
        string = re.sub(re.compile(r"\[ +", re.M), "[", string)
        string = re.sub(re.compile(r" +]", re.M), "]", string)
        return string

    @classmethod
    def clean_space(cls, string: str):
        if isinstance(string, str):
            string = cls._replace_re(string, cls._re_sub_unicode_space_patterns)
            string = re.sub(
                re.compile(r"\n\n^\*\*(.*?)\*\*$\n", re.M), lambda m: "\n\n**%s**\n\n" % m.group(1).strip(), string
            )
            string = re.sub(re.compile(r"^\*\*(( +#| #|#)+)", re.M), lambda m: "%s **" % m.group(1).strip(), string)
            return string
        return ""

    @classmethod
    def clean_punctuation(cls, string: str):
        if isinstance(string, str):
            for pattern, repl in cls._re_sub_punctuation_patterns:
                string = re.sub(pattern, repl, string)
        return string

    @classmethod
    def clean_emphasis(cls, string: str):
        string = re.sub(re.compile(r"\*\*(.*?)\*\*", re.M), lambda m: "**%s**" % m.group(1).strip(), string)
        string = re.sub(re.compile(r"__(.*?)__", re.M), lambda m: "__%s__" % m.group(1).strip(), string)
        string = re.sub(re.compile(r"_(.*?)_", re.M), lambda m: "_%s_" % m.group(1).strip(), string)
        return re.sub(re.compile(r"^[?!.,]+", re.M), "", string)

    @classmethod
    def delete_link(cls, string) -> str:
        if isinstance(string, str):
            matches = re.finditer(r"(?<!!)\[(.*?)]\(.*?\)", string, re.DOTALL | re.MULTILINE)
            for match in matches:
                repl = re.sub(r"\s+", " ", match.group(1).strip())
                string = string.replace(match.group(), repl)
            return string
        return string

    @classmethod
    def delete_image(cls, string) -> str:
        if isinstance(string, str):
            for match in cls.find_images(string):
                string = string.replace(match, "")
        return string

    @classmethod
    def clean_nested_ul(cls, string: str):
        for match in re.finditer(re.compile(r"^(\*| \*) +.*(\n {3,6}\*.*)+", re.M), string):
            match_str = match.group()
            headline, list_str = match_str.split("\n", maxsplit=1)
            headline = re.sub(re.compile(r"^\*"), "", headline.strip()).strip()
            headline = re.sub(re.compile(r"\*\*([a-zA-Z]).*\*\*"), lambda m: m.group(), headline.strip()).strip()
            headline = re.sub(re.compile(r"^\W+([a-zA-Z])"), lambda m: m.group().title(), headline)
            list_str = re.sub(re.compile(r"^ +", re.M), "", list_str)
            repl_str = "\n" + "\n\n".join([headline, list_str]) + "\n"
            string = string.replace(match_str, repl_str)

        return string

    @staticmethod
    def find_images(string) -> str:
        string = re.sub(r"(!\[.*?]\(.*)", r"\n\1", string, re.MULTILINE)
        matches = re.finditer(r"!\[.*]\(.*\n.*|!\[.*]\(.*", str(string), re.MULTILINE)
        for match in matches:
            yield match.group()