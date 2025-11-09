# Selector Models Guide

Complete guide to creating parser configurations for domain-specific HTML extraction.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Selector Syntax](#selector-syntax)
4. [Parent Scoping](#parent-scoping)
5. [Real-World Examples](#real-world-examples)
6. [Testing Selectors](#testing-selectors)

---

## Quick Start

### Step 1: Create Parser Config

Create a JSON file at `parsers/configs/{lang}/{char}/{domain}.json`:

```json
{
  "domain": "example.com",
  "lang": "en",
  "type": "article",
  "content": {
    "css_selector": "article",
    "type": "html"
  },
  "title": {
    "css_selector": "h1.title",
    "type": "text"
  },
  "authors": {
    "css_selector": ".author-name",
    "type": "text",
    "all": true
  }
}
```

### Step 2: Test Your Config

```python
from llm_scraper import Article
from llm_scraper.models.selector import ParserConfig
from pydantic import HttpUrl
import requests

# Load config
with open('parsers/configs/en/e/example.com.json') as f:
    config = ParserConfig.model_validate_json(f.read())

# Fetch and parse
html = requests.get('https://example.com/article').text
article = Article.from_html(html, HttpUrl('https://example.com/article'), parser_config=config)

print(f"Title: {article.title}")
print(f"Authors: {article.authors}")
```

---

## Architecture Overview

```
ParserConfig (domain-level)
  ├── domain: "example.com"
  ├── lang: "en"
  ├── type: "article"
  │
  ├── title: ElementSelector
  │     ├── css_selector: ["h1.title", "h1"]
  │     ├── type: "text"
  │     └── all: false
  │
  ├── authors: ElementSelector
  │     ├── css_selector: [
  │     │     {"selector": "a", "parent": ".byline"},
  │     │     ".author"
  │     │   ]
  │     ├── type: "text"
  │     └── all: true
  │
  └── content: ElementSelector (REQUIRED)
        ├── css_selector: "article"
        └── type: "html"
```

### Three Layers

1. **SelectorConfig** - Individual selector with options
   - `selector`: CSS selector string
   - `attribute`: Attribute to extract (optional)
   - `parent`: Parent element scope (optional)

2. **ElementSelector** - Field extraction config
   - `css_selector`: String or list of selectors/configs
   - `type`: "text" | "html" | "attribute"
   - `attribute`: Default attribute (optional)
   - `all`: Extract all matches (default: false)

3. **ParserConfig** - Complete domain config
   - `domain`, `lang`, `type` (metadata)
   - Field selectors (title, content, authors, etc.)
   - `cleanup`: Elements to remove
   - `sitemaps`, `rss_feeds`: Discovery URLs

---

## Selector Syntax

### 1. Simple String

```json
{
  "title": {
    "css_selector": "h1.article-title",
    "type": "text"
  }
}
```

### 2. Fallback Chain (Array of Strings)

```json
{
  "title": {
    "css_selector": [
      "h1.article-title",
      "h1.post-title",
      "h1"
    ],
    "type": "text"
  }
}
```

**How it works:**
1. Try `h1.article-title` → not found
2. Try `h1.post-title` → not found  
3. Try `h1` → **found!** ✅

### 3. Selector Config Objects

```json
{
  "date_published": {
    "css_selector": [
      {"selector": "time", "attribute": "datetime"},
      {"selector": "meta[property='article:published_time']", "attribute": "content"},
      ".publish-date"
    ],
    "type": "text"
  }
}
```

**How it works:**
1. Try `<time datetime="...">` → extract `datetime` attribute
2. If not found, try `<meta property="article:published_time" content="...">` → extract `content` attribute
3. If not found, try `.publish-date` → extract text

### 4. Mixed Syntax

```json
{
  "authors": {
    "css_selector": [
      {"selector": "a", "parent": ".byline"},
      ".author-name",
      "[rel='author']"
    ],
    "type": "text",
    "all": true
  }
}
```

---

## Parent Scoping

### Problem: False Matches

**HTML:**
```html
<nav>
  <a href="/about">About</a>
  <a href="/contact">Contact</a>
</nav>

<article>
  <div class="byline">
    <a href="/author/john">John Doe</a>
  </div>
  <div class="content">...</div>
</article>

<footer>
  <a href="/privacy">Privacy</a>
</footer>
```

**Without parent:**
```json
{
  "authors": {
    "css_selector": "a",
    "attribute": "href",
    "all": true
  }
}
```
**Result:** `["/about", "/contact", "/author/john", "/privacy"]` ❌ WRONG!

### Solution: Parent Scope

```json
{
  "authors": {
    "css_selector": [
      {"selector": "a", "attribute": "href", "parent": ".byline"}
    ],
    "type": "text",
    "all": true
  }
}
```
**Result:** `["/author/john"]` ✅ CORRECT!

### How Parent Works

**Flow:**
1. Find parent: `soup.select_one(".byline")` → `<div class="byline">`
2. Search within parent: `parent.select("a")` → `[<a href="/author/john">]`
3. Extract attribute: `href` → `/author/john`

### When to Use Parent

✅ **Use parent when:**
- Extracting from specific page sections (byline, sidebar, footer)
- Avoiding navigation/header/footer links
- Working with repeating structures
- Multiple similar elements on page

❌ **Don't need parent when:**
- Unique element (e.g., `<article>`, `<main>`)
- Specific class/ID (e.g., `.article-content`)
- No ambiguity

---

## Real-World Examples

### Example 1: News Article (Cointelegraph)

```json
{
  "domain": "cointelegraph.com",
  "lang": "en",
  "type": "article",
  
  "title": {
    "css_selector": ["h1.post__title", "h1.post-title", "h1"],
    "type": "text"
  },
  
  "content": {
    "css_selector": [".post-content", ".post__content", "article"],
    "type": "html"
  },
  
  "authors": {
    "css_selector": [
      ".post-meta__author-name",
      ".author-name",
      "[rel='author']"
    ],
    "type": "text",
    "all": true
  },
  
  "date_published": {
    "css_selector": [
      {"selector": "time", "attribute": "datetime"},
      {"selector": "meta[property='article:published_time']", "attribute": "content"}
    ],
    "type": "text"
  },
  
  "tags": {
    "css_selector": [
      "a[href*='/tags/']",
      ".tags__item a",
      "a[rel='tag']"
    ],
    "type": "text",
    "all": true
  },
  
  "cleanup": [
    ".ads-wrapper",
    ".newsletter-form",
    ".related-posts",
    ".social-share"
  ]
}
```

### Example 2: Blog with Parent Scoping

```json
{
  "domain": "techblog.com",
  "lang": "en",
  "type": "article",
  
  "title": {
    "css_selector": "h1.entry-title",
    "type": "text"
  },
  
  "content": {
    "css_selector": ".entry-content",
    "type": "html"
  },
  
  "authors": {
    "css_selector": [
      {"selector": "a", "parent": ".author-info"},
      {"selector": ".author-name", "parent": ".post-meta"}
    ],
    "type": "text",
    "all": true
  },
  
  "date_published": {
    "css_selector": [
      {"selector": "time", "attribute": "datetime", "parent": ".post-meta"},
      "time[datetime]"
    ],
    "type": "text"
  },
  
  "tags": {
    "css_selector": [
      {"selector": "a", "parent": ".tags-list"},
      "a.tag-link"
    ],
    "type": "text",
    "all": true
  },
  
  "follow_urls": {
    "css_selector": [
      {"selector": "a", "attribute": "href", "parent": ".related-posts"},
      {"selector": "a", "attribute": "href", "parent": ".recommended"}
    ],
    "type": "text",
    "all": true
  }
}
```

### Example 3: Multi-Language Site

```json
{
  "domain": "news.example.com",
  "lang": "vi",
  "type": "article",
  
  "title": {
    "css_selector": [
      "h1.tieu-de",
      "h1.title",
      "h1"
    ],
    "type": "text"
  },
  
  "content": {
    "css_selector": [
      ".noi-dung",
      ".content",
      "article"
    ],
    "type": "html"
  },
  
  "authors": {
    "css_selector": [
      {"selector": ".tac-gia", "parent": ".thong-tin"},
      ".author"
    ],
    "type": "text",
    "all": true
  },
  
  "date_published": {
    "css_selector": [
      {"selector": "time", "attribute": "datetime"},
      ".ngay-dang"
    ],
    "type": "text"
  }
}
```

---

## Testing Selectors

### Method 1: Python REPL

```python
from bs4 import BeautifulSoup
import requests

url = 'https://example.com/article'
html = requests.get(url).text
soup = BeautifulSoup(html, 'lxml')

# Test selector
elements = soup.select('.author-name')
print(f"Found {len(elements)} elements")
for el in elements:
    print(f"  - {el.get_text(strip=True)}")

# Test with parent
parent = soup.select_one('.byline')
if parent:
    authors = parent.select('a')
    print(f"Found {len(authors)} authors in byline")
```

### Method 2: Validation Script

```bash
python scripts/validate_article_fixture.py fixtures/en/e/example.com.json
```

**Output shows:**
- ✅ Which selectors matched
- ❌ Which selectors didn't match
- 📋 Extracted data preview

### Method 3: Browser DevTools

1. Open article page in browser
2. Press F12 → Console
3. Test selector:

```javascript
// Test selector
document.querySelectorAll('.author-name')

// Test with parent
const parent = document.querySelector('.byline');
parent.querySelectorAll('a');
```

---

## Common Patterns

### Pattern 1: Date Extraction

```json
{
  "date_published": {
    "css_selector": [
      {"selector": "time", "attribute": "datetime"},
      {"selector": "meta[property='article:published_time']", "attribute": "content"},
      {"selector": "meta[name='publish-date']", "attribute": "content"},
      ".publish-date",
      ".date"
    ],
    "type": "text"
  }
}
```

### Pattern 2: Image URL

```json
{
  "image_url": {
    "css_selector": [
      {"selector": "meta[property='og:image']", "attribute": "content"},
      {"selector": "img.featured-image", "attribute": "src"},
      {"selector": "img", "attribute": "src", "parent": ".article-header"}
    ],
    "type": "text"
  }
}
```

### Pattern 3: Multiple Authors

```json
{
  "authors": {
    "css_selector": [
      {"selector": "a", "parent": ".authors-list"},
      {"selector": "[rel='author']"},
      ".author-name"
    ],
    "type": "text",
    "all": true
  }
}
```

### Pattern 4: Tags from Multiple Sources

```json
{
  "tags": {
    "css_selector": [
      "a[href*='/tag/']",
      "a[href*='/tags/']",
      {"selector": "a", "parent": ".tags"},
      {"selector": "a", "parent": ".categories"},
      "a[rel='tag']"
    ],
    "type": "text",
    "all": true
  }
}
```

---

## Troubleshooting

### Problem: Selector not matching

**Check:**
1. Inspect HTML structure (F12 → Elements)
2. Verify CSS selector in browser console
3. Check if element is dynamically loaded (JavaScript)
4. Add fallback selectors

### Problem: Extracting wrong data

**Solutions:**
1. Use parent scoping to narrow search
2. Make selector more specific
3. Add unique class/attribute to selector

### Problem: Missing some elements

**Check:**
1. Is `"all": true` set?
2. Are elements within different parent containers?
3. Add multiple parent scopes

### Problem: Getting navigation links instead of content links

**Solution:**
```json
{
  "follow_urls": {
    "css_selector": [
      {"selector": "a", "attribute": "href", "parent": "article"},
      {"selector": "a", "attribute": "href", "parent": ".content"}
    ],
    "type": "text",
    "all": true
  }
}
```

---

## Best Practices

### ✅ DO

- Use fallback chains for robustness
- Add parent scope when needed
- Test selectors in browser first
- Use specific selectors when possible
- Add cleanup rules for ads/popups
- Document unusual selectors

### ❌ DON'T

- Rely on single selector (no fallbacks)
- Use overly generic selectors (e.g., `a`, `div`)
- Extract from navigation/footer by accident
- Forget to set `"all": true` for lists
- Leave test/debug selectors in production

---

## Directory Structure

```
src/llm_scraper/parsers/configs/
├── en/
│   ├── a/
│   ├── b/
│   ├── c/
│   │   └── cointelegraph.com.json
│   ├── ...
│   └── z/
├── vi/
│   ├── a/
│   └── ...
└── ...
```

**Naming convention:**
- `{lang}/{first-char}/{domain}.json`
- Example: `en/c/cointelegraph.com.json`
- Lowercase only

---

## Summary

**Three-level architecture:**
1. `SelectorConfig` - Individual selector options
2. `ElementSelector` - Field extraction config  
3. `ParserConfig` - Complete domain config

**Key features:**
- ✓ Fallback chains
- ✓ Per-selector attributes
- ✓ Parent scoping
- ✓ Multiple return values

**Parent scoping:**
- Solves false matches
- Narrows search scope
- Essential for complex pages

**Testing:**
- Browser DevTools
- Python REPL
- Validation script

**Next steps:**
1. Inspect target website HTML
2. Create parser config JSON
3. Test with validation script
4. Refine selectors as needed
