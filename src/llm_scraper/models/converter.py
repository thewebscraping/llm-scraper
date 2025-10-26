from __future__ import annotations

from bs4 import BeautifulSoup, NavigableString, Tag
from . import html as html_helpers

# A mapping from HTML tag names to our custom helper classes
TAG_HELPER_MAP = {
    "p": html_helpers.P,
    "div": html_helpers.Div,
    "span": html_helpers.Span,
    "a": html_helpers.A,
    "img": html_helpers.Img,
    "br": html_helpers.BR,
    "hr": html_helpers.HR,
    "h1": html_helpers.H1,
    "h2": html_helpers.H2,
    "h3": html_helpers.H3,
    "h4": html_helpers.H4,
    "h5": html_helpers.H5,
    "h6": html_helpers.H6,
    "strong": html_helpers.Strong,
    "b": html_helpers.BTag,
    "em": html_helpers.Em,
    "i": html_helpers.Italic,
    "u": html_helpers.U,
    "del": html_helpers.Del,
    "s": html_helpers.S,
    "strike": html_helpers.Strike,
    "code": html_helpers.Code,
    "pre": html_helpers.Pre,
    "blockquote": html_helpers.Blockquote,
    "ul": html_helpers.UL,
    "ol": html_helpers.OL,
    "li": html_helpers.LI,
    "table": html_helpers.Table,
    "thead": html_helpers.THead,
    "tbody": html_helpers.TBody,
    "tfoot": html_helpers.TFoot,
    "tr": html_helpers.TR,
    "th": html_helpers.TH,
    "td": html_helpers.TD,
    "caption": html_helpers.Caption,
    # Tags to be ignored (converted to empty string)
    "script": html_helpers.Script,
    "style": html_helpers.Style,
    "noscript": html_helpers.NoScript,
    "iframe": html_helpers.IFrame,
    "head": html_helpers.Head,
}


class MarkdownConverter:
    def __init__(self, **options):
        self.options = options

    def convert(self, html: str) -> str:
        """
        Converts HTML to Markdown using BeautifulSoup for parsing.
        """
        soup = BeautifulSoup(html, "lxml")
        return self.process_node(soup)

    def process_node(self, node: Tag | NavigableString) -> str:
        """
        Recursively processes a BeautifulSoup node (Tag or String) and converts it to Markdown.
        """
        # If it's a string, just return it
        if isinstance(node, NavigableString):
            return str(node)

        # If it's a tag, process its children first (post-order traversal)
        processed_children_text = "".join(self.process_node(child) for child in node.children)

        # Find the appropriate helper class for this tag
        helper_class = TAG_HELPER_MAP.get(node.name)

        # If no specific helper, treat it as a generic tag (like a div or span)
        # and just return the processed text of its children.
        if not helper_class:
            return processed_children_text

        # Create an instance of the helper with the tag and its processed children text
        helper_instance = self.create_helper_instance(helper_class, node, processed_children_text)

        # Let the helper class perform its specific markdown conversion
        return helper_instance.to_markdown()

    def create_helper_instance(self, helper_class, tag: Tag, text: str):
        """
        Creates an instance of an HTMLHelper subclass, configured with the bs4 tag
        and the processed text from its children.
        """
        return helper_class(tag=tag, processed_text=text)


def html_to_markdown(html: str, **options) -> str:
    """
    Main function to convert HTML string to Markdown.
    """
    converter = MarkdownConverter(**options)
    markdown = converter.convert(html)
    
    # Final post-processing steps from your original MarkdownHelper
    markdown = html_helpers.HTMLHelper.decode_tag(markdown)
    # Add any other final cleaning steps here if needed
    
    return markdown.strip()
