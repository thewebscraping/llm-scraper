#!/usr/bin/env python3
"""
Fetch a URL and create a fixture file for testing.

This script:
1. Fetches HTML content from a URL using tls_requests
2. Extracts domain name and creates appropriate directory structure
3. Saves fixture in fixtures/{lang}/{first_char}/{domain}.json format
4. Allows easy testing with validate_article_fixture.py

Usage:
  python scripts/fetch_and_create_fixture.py <url> [--lang en]
  
Example:
  python scripts/fetch_and_create_fixture.py https://crypto.news/the-next-standard-in-blockchain-is-code-neutrality/
  python scripts/fetch_and_create_fixture.py https://cointelegraph.com/news/some-article --lang en
"""
from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path
from urllib.parse import urlparse
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


def fetch_html(url: str) -> str:
    """Fetch HTML content from URL using tls_requests."""
    print(f"🌐 Fetching: {url}")
    
    try:
        with tls_requests.Client(
            timeout=20.0,
            follow_redirects=True
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Get final URL after redirects
            final_url = str(response.url)
            if final_url != url:
                print(f"   ↳ Redirected to: {final_url}")
            
            print(f"✅ Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"   Content-Length: {len(response.text):,} bytes")
            
            return response.text
    except tls_requests.HTTPError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        raise SystemExit(2)
    except Exception as e:
        print(f"❌ Error fetching URL: {e}")
        raise SystemExit(2)


def create_fixture(url: str, html: str, lang: str = "en") -> Path:
    """
    Create fixture file with URL, domain, and raw HTML.
    
    Returns:
        Path to the created fixture file.
    """
    domain = extract_domain(url)
    fixture_path = get_fixture_path(domain, lang)
    
    fixture_data = {
        "url": url,
        "domain": domain,
        "raw_html": html
    }
    
    print("\n💾 Creating fixture:")
    print(f"   Domain: {domain}")
    print(f"   Path: {fixture_path}")
    
    # Write fixture file
    fixture_path.write_text(
        json.dumps(fixture_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    
    print(f"✅ Fixture created: {fixture_path}")
    return fixture_path


def check_parser_config(domain: str, lang: str = "en") -> bool:
    """Check if parser config exists for this domain."""
    first_char = domain[0].lower()
    config_path = Path(f"src/llm_scraper/parsers/configs/{lang}/{first_char}/{domain}.json")
    
    if config_path.exists():
        print(f"\n✅ Parser config found: {config_path}")
        
        # Show selector info
        try:
            config_data = json.loads(config_path.read_text())
            print("   Configured fields:")
            for field in ['title', 'description', 'content', 'authors', 'date_published', 'tags']:
                if field in config_data:
                    selector_field = config_data[field].get('selector', config_data[field].get('css_selector', []))
                    if isinstance(selector_field, list) and selector_field:
                        print(f"   - {field}: {selector_field[0]}")
        except Exception as e:
            print(f"   (Could not parse config: {e})")
        
        return True
    else:
        print(f"\n⚠️  No parser config found: {config_path}")
        print("   You may need to create one for optimal extraction.")
        return False


def suggest_next_steps(fixture_path: Path, has_config: bool):
    """Print suggestions for next steps."""
    print("\n" + "=" * 60)
    print("📋 Next Steps:")
    print("=" * 60)
    
    print("\n1. Validate the fixture:")
    print(f"   python scripts/validate_article_fixture.py {fixture_path}")
    
    if not has_config:
        domain = fixture_path.stem  # filename without extension
        first_char = domain[0].lower()
        config_path = f"src/llm_scraper/parsers/configs/en/{first_char}/{domain}.json"
        print("\n2. Create parser config (recommended):")
        print(f"   Edit: {config_path}")
        print("   Use XPath selectors for better precision!")
    
    print("\n3. Test extraction and iterate:")
    print("   - Run validation script")
    print("   - Check extracted fields (title, content, tags, etc.)")
    print("   - Update parser config if needed")
    print("   - Re-run validation")
    
    print("\n💡 Tips:")
    print("   - Use XPath for attribute-based selection: //time[@datetime]/@datetime")
    print("   - Use CSS for simple class/id selection: .article-title")
    print("   - Add fallback chains: [xpath, css, another-css]")
    print("   - Test with: python scripts/validate_article_fixture.py")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch URL and create fixture file for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://crypto.news/article-slug/
  %(prog)s https://cointelegraph.com/news/article-slug --lang en
  
The fixture will be saved to:
  fixtures/{lang}/{first_char}/{domain}.json
  
You can then validate it with:
  python scripts/validate_article_fixture.py fixtures/en/c/crypto.news.json
        """
    )
    
    parser.add_argument(
        "url",
        help="URL to fetch and create fixture from"
    )
    
    parser.add_argument(
        "--lang",
        default="en",
        help="Language code for fixture directory (default: en)"
    )
    
    args = parser.parse_args(argv[1:])
    
    # Validate URL
    try:
        parsed = urlparse(args.url)
        if not parsed.scheme or not parsed.netloc:
            print(f"❌ Invalid URL: {args.url}")
            return 65
    except Exception as e:
        print(f"❌ Invalid URL: {e}")
        return 65
    
    print("=" * 60)
    print("🔧 Fetch and Create Fixture")
    print("=" * 60)
    
    # Fetch HTML
    html = fetch_html(args.url)
    
    # Create fixture
    fixture_path = create_fixture(args.url, html, args.lang)
    
    # Check for parser config
    domain = extract_domain(args.url)
    has_config = check_parser_config(domain, args.lang)
    
    # Suggest next steps
    suggest_next_steps(fixture_path, has_config)
    
    print("\n✨ Done!\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
