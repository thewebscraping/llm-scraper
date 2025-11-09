#!/usr/bin/env python3
"""
Debug HTML structure of fixtures to find correct selectors.
"""
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def debug_site(fixture_path: Path):
    """Debug a single site's HTML structure."""
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
    
    # 2. Find content area
    print("\n2. ARTICLE CONTENT:")
    print("-" * 40)
    main_article = soup.find('article') or soup.find('main')
    if main_article:
        for sel in [
            '.entry-content',
            '.post-content', 
            '.article-content',
            '.article-body',
            '[itemprop="articleBody"]',
            'div.content',
            '.post__content',
            '.td-post-content'
        ]:
            elem = main_article.select_one(sel)
            if elem:
                # Get paragraphs
                paragraphs = elem.find_all('p', recursive=True)
                texts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
                word_count = sum(len(t.split()) for t in texts)
                
                print(f"  ✓ {sel}:")
                print(f"    Paragraphs: {len(texts)}")
                print(f"    Words: {word_count}")
                if texts:
                    print(f"    First para: {texts[0][:120]}...")
    else:
        print("  ✗ No main article/main element found")
    
    # 3. Find authors
    print("\n3. AUTHORS:")
    print("-" * 40)
    for sel in [
        'a[rel="author"]',
        '[rel="author"]',
        '.author-name',
        '.post-author',
        '[class*="author"]',
        '[itemprop="author"]'
    ]:
        elems = soup.select(sel)
        if elems:
            authors = [e.get_text(strip=True) for e in elems[:3]]
            # Clean up authors (remove extra info)
            authors = [a.split('\n')[0].split('·')[0].strip() for a in authors if a]
            if authors:
                print(f"  ✓ {sel}: {authors[:3]}")
    
    # 4. Find tags
    print("\n4. TAGS:")
    print("-" * 40)
    for sel in [
        'a[rel="tag"]',
        '[rel="tag"]',
        '.post-tags a',
        '.tags a',
        '[class*="tag"] a',
        'a[href*="/tag/"]',
        'a[href*="/tags/"]'
    ]:
        elems = soup.select(sel)
        if elems:
            tags = [e.get_text(strip=True) for e in elems[:10]]
            tags = [t for t in tags if t and len(t) > 1]
            if tags:
                print(f"  ✓ {sel}: {tags[:5]}")
    
    # 5. Find date
    print("\n5. PUBLISHED DATE:")
    print("-" * 40)
    for sel in [
        'time[datetime]',
        'time',
        '.published',
        '.entry-date',
        '[itemprop="datePublished"]',
        '[class*="date"]'
    ]:
        elems = soup.select(sel)
        if elems:
            dates = []
            for e in elems[:3]:
                dt = e.get('datetime') or e.get('content') or e.get_text(strip=True)
                if dt:
                    dates.append(dt)
            if dates:
                print(f"  ✓ {sel}: {dates[:2]}")


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
