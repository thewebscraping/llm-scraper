#!/usr/bin/env python3
"""
Debug HTML structure of fixtures to find correct selectors.
Uses presets from llm_scraper.presets for comprehensive testing.
"""
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# Try to import presets
try:
    sys.path.insert(0, str(Path.cwd() / "src"))
    from llm_scraper.presets import (
        TITLE_SELECTORS,
        CONTENT_SELECTORS,
        AUTHOR_SELECTORS,
        DATE_PUBLISHED_SELECTORS,
        TAGS_SELECTORS,
    )
except ImportError:
    print("⚠️ Could not import presets, using fallback selectors")
    TITLE_SELECTORS = ["h1.article-title", "h1"]
    CONTENT_SELECTORS = [".article-content", "article"]
    AUTHOR_SELECTORS = ["a[rel='author']", ".author-name"]
    DATE_PUBLISHED_SELECTORS = ["time[datetime]", "time"]
    TAGS_SELECTORS = ["a[rel='tag']", ".tags a"]


def debug_site(fixture_path: Path):
    """Debug a single site's HTML structure using preset selectors."""
    data = json.loads(fixture_path.read_text())
    url = data.get('url', 'N/A')
    domain = data.get('domain', 'N/A')
    
    print(f"\n{'='*80}")
    print(f"SITE: {domain}")
    print(f"URL: {url}")
    print(f"{'='*80}\n")
    
    soup = BeautifulSoup(data['raw_html'], 'html.parser')
    
    # 1. Find main article container
    print("1. MAIN ARTICLE CONTAINER:")
    print("-" * 40)
    for sel in ['article', 'main article', '[role="main"]', '.post', '.article']:
        elems = soup.select(sel)
        if elems:
            print(f"  ✓ {sel}: {len(elems)} element(s)")
            # Get first one's classes and id
            first = elems[0]
            elem_id = first.get('id', '')
            elem_classes = ' '.join(first.get('class', []))
            if elem_id:
                print(f"    ID: {elem_id}")
            if elem_classes:
                print(f"    Classes: {elem_classes}")
    
    # 2. Find title using presets
    print("\n2. ARTICLE TITLE (from presets):")
    print("-" * 40)
    for sel in TITLE_SELECTORS[:10]:  # Test top 10
        elems = soup.select(sel)
        if elems:
            title_text = elems[0].get_text(strip=True)
            if title_text:
                print(f"  ✓ {sel}: {title_text[:60]}...")
                break  # Found title, stop
    
    # 3. Find content area using presets
    print("\n3. ARTICLE CONTENT (from presets):")
    print("-" * 40)
    for sel in CONTENT_SELECTORS[:10]:  # Test top 10
        elems = soup.select(sel)
        if elems:
            elem = elems[0]
            paragraphs = elem.find_all('p', recursive=True)
            texts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
            word_count = sum(len(t.split()) for t in texts)
            
            if word_count > 100:  # Only show if substantial content
                print(f"  ✓ {sel}:")
                print(f"    Paragraphs: {len(texts)}")
                print(f"    Words: {word_count}")
                if texts:
                    print(f"    First para: {texts[0][:120]}...")
                break  # Found content, stop
    
    # 4. Find authors using presets
    print("\n4. AUTHORS (from presets):")
    print("-" * 40)
    for sel in AUTHOR_SELECTORS[:10]:  # Test top 10
        elems = soup.select(sel)
        if elems:
            authors = [e.get_text(strip=True) for e in elems[:3]]
            # Clean up authors (remove extra info)
            authors = [a.split('\n')[0].split('·')[0].strip() for a in authors if a]
            if authors:
                print(f"  ✓ {sel}: {authors[:3]}")
                break  # Found authors, stop
    
    # 5. Find tags using presets
    print("\n5. TAGS (from presets):")
    print("-" * 40)
    for sel in TAGS_SELECTORS[:10]:  # Test top 10
        elems = soup.select(sel)
        if elems:
            tags = [e.get_text(strip=True) for e in elems[:10]]
            tags = [t for t in tags if t and len(t) > 1]
            if tags:
                print(f"  ✓ {sel}: {tags[:5]}")
                break  # Found tags, stop
    
    # 6. Find date using presets
    print("\n6. PUBLISHED DATE (from presets):")
    print("-" * 40)
    for sel in DATE_PUBLISHED_SELECTORS[:10]:  # Test top 10
        elems = soup.select(sel)
        if elems:
            dates = []
            for e in elems[:3]:
                dt = e.get('datetime') or e.get('content') or e.get_text(strip=True)
                if dt:
                    dates.append(dt)
            if dates:
                print(f"  ✓ {sel}: {dates[:2]}")
                break  # Found dates, stop


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Debug specific file
        fixture_path = Path(sys.argv[1])
        if fixture_path.exists():
            debug_site(fixture_path)
        else:
            print(f"File not found: {fixture_path}")
    else:
        # Debug all fixtures
        fixtures = [
            'fixtures/en/c/cryptoslate.com.json',
            'fixtures/en/c/coindesk.com.json',
            'fixtures/en/c/cryptonews.com.json',
            'fixtures/en/t/theblock.co.json',
            'fixtures/en/c/cryptonews.net.json'
        ]
        
        for fixture_file in fixtures:
            path = Path(fixture_file)
            if path.exists():
                debug_site(path)
