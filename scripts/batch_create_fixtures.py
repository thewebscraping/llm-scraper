#!/usr/bin/env python3
"""
Batch create fixtures from a list of URLs.

This script fetches multiple URLs and creates fixture files for each.
Includes retry logic and error handling.

Usage:
  python scripts/batch_create_fixtures.py <urls_file>
  python scripts/batch_create_fixtures.py --urls url1 url2 url3
  
Example:
  python scripts/batch_create_fixtures.py urls.txt
  python scripts/batch_create_fixtures.py --urls https://crypto.news/article/ https://cointelegraph.com/news/article/
"""
from __future__ import annotations

import sys
import json
import argparse
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Optional
import tls_requests


def extract_domain(url: str) -> str:
    """Extract domain from URL (e.g., 'crypto.news' from full URL)."""
    parsed = urlparse(url)
    domain = parsed.netloc
    # Remove www. prefix if present
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


def get_fixture_path(domain: str, lang: str = "en") -> Path:
    """
    Get the fixture file path based on domain.
    
    Format: fixtures/{lang}/{first_char}/{domain}.json
    Example: fixtures/en/c/crypto.news.json
    """
    first_char = domain[0].lower()
    fixture_dir = Path(f"fixtures/{lang}/{first_char}")
    fixture_dir.mkdir(parents=True, exist_ok=True)
    return fixture_dir / f"{domain}.json"


def fetch_html_with_retry(url: str, max_retries: int = 3, delay: float = 2.0) -> Optional[str]:
    """
    Fetch HTML content from URL using tls_requests with retry logic.
    
    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts (default: 3)
        delay: Delay between retries in seconds (default: 2.0)
    
    Returns:
        HTML content as string, or None if all retries failed
    """
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   Attempt {attempt}/{max_retries}...", end=" ")
            
            with tls_requests.Client(
                timeout=20.0,
                follow_redirects=True
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                
                print(f"✅ {response.status_code} ({len(response.text):,} bytes)")
                return response.text
                
        except tls_requests.HTTPError as e:
            print(f"❌ HTTP {e.response.status_code}")
            if attempt < max_retries:
                print(f"   Retrying in {delay}s...")
                time.sleep(delay)
            continue
            
        except Exception as e:
            print(f"❌ Error: {e}")
            if attempt < max_retries:
                print(f"   Retrying in {delay}s...")
                time.sleep(delay)
            continue
    
    return None


def create_fixture(url: str, html: str, lang: str = "en") -> Optional[Path]:
    """
    Create fixture file with URL, domain, and raw HTML.
    
    Returns:
        Path to the created fixture file, or None if failed.
    """
    try:
        domain = extract_domain(url)
        fixture_path = get_fixture_path(domain, lang)
        
        fixture_data = {
            "url": url,
            "domain": domain,
            "raw_html": html
        }
        
        # Write fixture file
        fixture_path.write_text(
            json.dumps(fixture_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        return fixture_path
    except Exception as e:
        print(f"   ❌ Failed to create fixture: {e}")
        return None


def check_or_create_parser_config(domain: str, lang: str = "en") -> Path:
    """
    Check if parser config exists, create template if not.
    
    Returns:
        Path to the parser config (existing or newly created)
    """
    first_char = domain[0].lower()
    config_path = Path(f"src/llm_scraper/parsers/configs/{lang}/{first_char}/{domain}.json")
    
    if config_path.exists():
        return config_path
    
    # Create template config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    template_config = {
        "domain": domain,
        "lang": lang,
        "type": "article",
        "title": {
            "selector": [
                "h1.article-title",
                "h1.post-title",
                "h1"
            ],
            "type": "text"
        },
        "description": {
            "selector": [
                ".article-excerpt",
                ".post-excerpt",
                "meta[name='description']"
            ],
            "type": "text"
        },
        "content": {
            "selector": [
                ".article-content",
                ".post-content",
                "article"
            ],
            "type": "html"
        },
        "authors": {
            "selector": [
                "//a[@rel='author']",
                ".author-name"
            ],
            "type": "text",
            "all": True
        },
        "date_published": {
            "selector": [
                "//time[@datetime]/@datetime",
                "//meta[@property='article:published_time']/@content",
                "time[datetime]"
            ],
            "type": "text",
            "attribute": "datetime"
        },
        "tags": {
            "selector": [
                "//a[@rel='tag']",
                "//a[contains(@href, '/tag/')]",
                ".post-tags a"
            ],
            "type": "text",
            "all": True
        },
        "cleanup": [
            ".ads",
            ".advertisement",
            ".related-posts",
            ".newsletter",
            ".social-share"
        ]
    }
    
    config_path.write_text(
        json.dumps(template_config, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    return config_path


def process_url(url: str, lang: str = "en", max_retries: int = 3) -> bool:
    """
    Process a single URL: fetch, create fixture, ensure config exists.
    
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"🌐 {url}")
    print(f"{'='*60}")
    
    # Extract domain
    domain = extract_domain(url)
    print(f"Domain: {domain}")
    
    # Fetch HTML with retry
    html = fetch_html_with_retry(url, max_retries=max_retries)
    if html is None:
        print(f"❌ Failed to fetch after {max_retries} attempts - SKIPPING")
        return False
    
    # Create fixture
    fixture_path = create_fixture(url, html, lang)
    if fixture_path is None:
        print("❌ Failed to create fixture - SKIPPING")
        return False
    
    print(f"✅ Fixture: {fixture_path}")
    
    # Check/create parser config
    config_path = check_or_create_parser_config(domain, lang)
    if config_path.exists():
        # Check if it's newly created
        config_data = json.loads(config_path.read_text())
        if config_data.get("domain") == domain and "article-title" in str(config_data.get("title", {})):
            print(f"📝 Config (template): {config_path}")
        else:
            print(f"✅ Config (existing): {config_path}")
    
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Batch create fixtures from multiple URLs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s urls.txt
  %(prog)s --urls https://crypto.news/article/ https://cointelegraph.com/news/article/
  
After running, validate each fixture:
  python scripts/validate_article_fixture.py fixtures/en/c/domain.json
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "file",
        nargs="?",
        help="Text file with URLs (one per line)"
    )
    group.add_argument(
        "--urls",
        nargs="+",
        help="List of URLs to process"
    )
    
    parser.add_argument(
        "--lang",
        default="en",
        help="Language code for fixture directory (default: en)"
    )
    
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts per URL (default: 3)"
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    
    args = parser.parse_args(argv[1:])
    
    # Get URLs from file or command line
    urls: List[str] = []
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return 66
        
        urls = [
            line.strip()
            for line in file_path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        urls = args.urls
    
    if not urls:
        print("❌ No URLs to process")
        return 1
    
    print("=" * 60)
    print("🚀 Batch Create Fixtures")
    print("=" * 60)
    print(f"URLs to process: {len(urls)}")
    print(f"Max retries: {args.max_retries}")
    print(f"Delay between requests: {args.delay}s")
    
    # Process each URL
    results = {
        "success": [],
        "failed": []
    }
    
    for i, url in enumerate(urls, 1):
        if i > 1 and args.delay > 0:
            print(f"\n⏳ Waiting {args.delay}s before next request...")
            time.sleep(args.delay)
        
        print(f"\n[{i}/{len(urls)}]")
        success = process_url(url, lang=args.lang, max_retries=args.max_retries)
        
        if success:
            results["success"].append(url)
        else:
            results["failed"].append(url)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    print(f"✅ Successful: {len(results['success'])}/{len(urls)}")
    print(f"❌ Failed: {len(results['failed'])}/{len(urls)}")
    
    if results["failed"]:
        print("\n❌ Failed URLs:")
        for url in results["failed"]:
            print(f"   - {url}")
    
    if results["success"]:
        print("\n📋 Next Steps:")
        print("   1. Validate fixtures:")
        for url in results["success"]:
            domain = extract_domain(url)
            first_char = domain[0].lower()
            print(f"      python scripts/validate_article_fixture.py fixtures/en/{first_char}/{domain}.json")
        
        print("\n   2. Update parser configs as needed")
        print("   3. Re-validate to ensure extraction works correctly")
    
    print("\n✨ Done!\n")
    
    return 0 if results["failed"] == [] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
