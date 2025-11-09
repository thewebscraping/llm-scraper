from .models.selector import ElementSelector, ParserConfig

# =====================================================================================
# PRE-BUILT SELECTORS FOR COMMON ELEMENTS
# These can be reused across different parser configurations.
# =====================================================================================

# Common selectors for removing boilerplate/unwanted content
COMMON_CLEANUP_SELECTORS = [
    # Advertisements and popups
    ".ads-center",
    ".ads_middle",
    ".adscontent",
    ".adv",
    ".ap_container",
    ".google-ads",
    ".google-auto-placed",
    ".popup",
    ".popup-detail-content",
    # Social sharing, related articles, and other clutter
    ".related",
    ".social-bar",
    ".sponsor",
    ".table-of-contents",
    ".toc-plus",
    ".toc-subnav",
    ".tts-player",
    ".youtube-video",
    # Common nuisance classes
    ".print-link",
    ".comment-links",
    "figure.wp-block-embed",
    # WordPress specific
    ".tdb_single_content .tdb-block-inner.td-fix-index",
]

# Selectors for article titles
TITLE_SELECTORS = [
    ".article_title",
    ".article__title",
    ".article-title",
    ".cms-title",
    ".kbwc-title",
    ".text-title",
    ".the-article-title",
    ".tmp-title-large",
    ".main-title",
    ".main-title-super",
    ".detail-title",
    ".news-title",
    ".content-detail-title",
    ".single-page-title",  # WordPress
    ".tdb-title-text",  # WordPress (Theme-specific)
    "h1",  # Generic fallback
]

# Selectors for main article content
CONTENT_SELECTORS = [
    ".ContentDetail",
    ".art-body",
    ".article-content",
    ".cate-24h-foot-arti-deta-info",
    ".article__body",
    ".detail-body",
    ".detail-content",
    ".fck_detail",
    ".the-article-content",
    ".tmp-entry-content",
    ".zce-content-body",
    ".txt_content",
    ".edittor-content",
    ".content_detailnews",
    ".afcbc-body",  # Sapo
    ".cms-body",  # Sapo
    ".knc-content",  # Sapo
    ".singular-content",  # Sapo
    ".sapo_detail",  # Sapo
    ".entry-body",  # Sapo
    ".tdb_single_content",  # WordPress
    ".single-post-content",  # WordPress
    "[itemprop='articleBody']",
    "article",  # Generic fallback
    "main",  # Generic fallback
]

# Selectors for authors
AUTHOR_SELECTORS = [
    ".article__author",
    ".author-name",
    ".author-title",
    ".authorName",
    ".cms-author",
    ".content-author",
    ".kbwcm-author",
    ".name-author",
    ".wrap-author",
    ".link_author",
    ".author-info",
    ".detail__author",
    ".author",
    ".authors",
    ".txt-name",
    "[rel='author']",
]

# Selectors for publication dates
DATE_PUBLISHED_SELECTORS = [
    "time[itemprop='datePublished']",
    "time[property='article:published_time']",
    "meta[property='article:published_time']",
    "time",
    "[data-role='publishdate']",
    ".detail-time",
    ".author-time",
    ".post-time",
]

# Selectors for modification dates
DATE_MODIFIED_SELECTORS = [
    "time[itemprop='dateModified']",
    "meta[property='article:modified_time']",
]

# Selectors for tags/keywords
TAGS_SELECTORS = [
    "a[rel='tag']",
    ".tdb-tags a",  # WordPress
    ".tags a",
    ".tag a",
]

# =====================================================================================
# PRESET PARSER CONFIGURATIONS
# These combine the selectors above into ready-to-use configs.
# =====================================================================================


def _create_selector(selectors: list[str], all_matches: bool = False) -> ElementSelector:
    """Helper to create an ElementSelector from a prioritized list of CSS selectors."""
    return ElementSelector(selector=selectors, all=all_matches)


# A generic, fallback configuration that tries common selectors.
GENERIC_CONFIG = ParserConfig(
    domain="generic",
    lang="en",
    type="article",
    title=_create_selector(TITLE_SELECTORS),
    content=_create_selector(CONTENT_SELECTORS),
    authors=_create_selector(AUTHOR_SELECTORS),
    date_published=_create_selector(DATE_PUBLISHED_SELECTORS),
    date_modified=_create_selector(DATE_MODIFIED_SELECTORS),
    tags=_create_selector(TAGS_SELECTORS, all_matches=True),
    cleanup=COMMON_CLEANUP_SELECTORS,
)

# A configuration specifically tuned for many WordPress sites.
WORDPRESS_CONFIG = ParserConfig(
    domain="wordpress",
    lang="en",
    type="article",
    title=_create_selector([
        ".tdb-title-text",
        ".single-page-title",
        ".entry-title",
        ".post-title",
    ] + TITLE_SELECTORS),
    content=_create_selector([
        ".tdb_single_content",
        ".single-post-content",
        ".entry-content",
        ".post-content",
    ] + CONTENT_SELECTORS),
    authors=_create_selector([
        ".tdb-author-name",
        ".author-box .author-name",
    ] + AUTHOR_SELECTORS),
    tags=_create_selector([
        ".tdb-tags a",
        ".tags-links a",
    ] + TAGS_SELECTORS, all_matches=True),
    cleanup=COMMON_CLEANUP_SELECTORS + [
        ".td-post-sharing-top",
        ".td-post-sharing-bottom",
        ".td-g-rec",
        ".ez-toc-container",
    ],
)
