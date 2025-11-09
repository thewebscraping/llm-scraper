# XPath Selector Support

## Overview

Feature branch adding **XPath expression support** alongside existing CSS selectors for more powerful HTML element extraction.

## What's New

### 1. **SelectorType Enum**
```python
from llm_scraper import SelectorType

SelectorType.CSS    # CSS selectors: "div.content", "#main > p"
SelectorType.XPATH  # XPath expressions: "//div[@class='content']", "//p[1]"
SelectorType.AUTO   # Auto-detect based on query syntax
```

### 2. **Enhanced SelectorConfig**
```python
# CSS selector with attribute
{
    "query": "time",
    "selector_type": "css",
    "attribute": "datetime"
}

# XPath expression
{
    "query": "//time[@class='published']",
    "selector_type": "xpath",
    "attribute": "datetime"
}

# Auto-detect (XPath because starts with //)
{
    "query": "//article/div[@class='content']",
    "selector_type": "auto"  # or omit (defaults to AUTO)
}
```

### 3. **Mixed CSS and XPath in ElementSelector**
```python
from llm_scraper import ElementSelector

# Mix CSS and XPath in fallback chains
selector = ElementSelector(
    selector=[
        "h2.missing",                              # CSS (will fail)
        "//h1[@class='post-title']",              # XPath (will succeed)
        "h1"                                      # CSS fallback
    ],
    type="text"
)
```

### 4. **Parent Scoping with Both Selector Types**
```python
# CSS parent with CSS child
{
    "query": "a",
    "selector_type": "css",
    "parent": ".byline"
}

# XPath parent with XPath child
{
    "query": ".//a[@rel='author']",
    "selector_type": "xpath",
    "parent": "//div[@class='byline']"
}

# Mixed: CSS child in XPath parent
{
    "query": "a.author",
    "selector_type": "css",
    "parent": "//div[@class='post-meta']"
}
```

## XPath Advantages

XPath provides more powerful selection capabilities than CSS:

- **Ancestor/descendant navigation**: `"//div[@class='post']//h1"`
- **Attribute-based filtering**: `"//a[@rel='author']"`
- **Position-based selection**: `"//p[1]"`, `"//li[last()]"`
- **Text content matching**: `"//span[contains(text(), 'Published')]"`
- **Boolean logic**: `"//div[@class='post' and @data-type='article']"`

## Real-World Examples

### Extract Authors with Fallbacks
```python
from llm_scraper import ParserConfig, ElementSelector

config = ParserConfig(
    domain="example.com",
    content=ElementSelector(selector="article", type="html"),
    authors=ElementSelector(
        selector=[
            # Try XPath in specific parent first
            {"query": ".//a[@rel='author']", "selector_type": "xpath", "parent": "//div[@class='byline']"},
            # Fallback to CSS
            {"query": "a", "selector_type": "css", "parent": ".byline"},
            # Last resort
            ".author"
        ],
        type="text",
        all=True
    )
)
```

### Extract Date Published
```python
date_selector = ElementSelector(
    selector=[
        # Try CSS with datetime attribute
        {"query": "time", "selector_type": "css", "attribute": "datetime"},
        # Try XPath with pubdate attribute
        {"query": "//time[@pubdate]", "selector_type": "xpath", "attribute": "datetime"},
        # Fallback to meta tag
        {"query": "meta[property='article:published_time']", "attribute": "content"}
    ],
    type="text"
)
```

### Extract Tags from Specific Section
```python
tags_selector = ElementSelector(
    selector=[
        # XPath within XPath parent
        {"query": ".//a", "selector_type": "xpath", "parent": "//div[@class='tags']"},
        # CSS fallback
        "a[rel='tag']"
    ],
    type="text",
    all=True
)
```

## Auto-Detection

The system automatically detects selector type:

```python
# These are automatically recognized as XPath (start with / or //)
"//div[@class='content']"
"/html/body/article"

# These are recognized as CSS
"div.content"
"article > div"
"#main .post"
```

## Migration Guide

### Before (CSS only)
```python
ElementSelector(
    css_selector="div.content",  # Old field name
    type="html"
)
```

### After (CSS and XPath support)
```python
ElementSelector(
    selector="div.content",  # New field name
    type="html"
)

# Or use XPath
ElementSelector(
    selector="//div[@class='content']",
    type="html"
)
```

**Note**: `css_selector` field is replaced with `selector` to be generic.

## Testing

Comprehensive test suite with 18 tests covering:
- ✅ Pure CSS selectors
- ✅ Pure XPath expressions  
- ✅ Mixed CSS + XPath fallback chains
- ✅ Parent scoping with both types
- ✅ Auto-detection
- ✅ Complex real-world scenarios

Run tests:
```bash
pytest tests/test_xpath_selector.py -v
```

## Implementation Details

- **lxml** library used for XPath support (already in dependencies)
- BeautifulSoup tree converted to lxml tree for XPath queries
- Fallback chain stops at first successful selector
- Parent scoping works with both CSS and XPath
- All existing CSS functionality preserved

## Breaking Changes

⚠️ **Field rename**: `css_selector` → `selector` in `ElementSelector`

Update your code:
```python
# Old
ElementSelector(css_selector="div.content")

# New  
ElementSelector(selector="div.content")
```

## Benefits

✅ **More powerful selection**: XPath can do things CSS cannot  
✅ **Backward compatible**: All CSS selectors still work  
✅ **Flexible fallbacks**: Mix CSS and XPath in same config  
✅ **Auto-detection**: No need to specify type manually  
✅ **Parent scoping**: Works with both selector types  
✅ **Battle-tested**: 18 comprehensive tests

## Next Steps

- Merge to `main` after review
- Update documentation
- Add more real-world examples
- Consider XPath support in `cleanup` selectors
