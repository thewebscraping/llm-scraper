#!/usr/bin/env python3
"""
Dump all schema.org JSON-LD blocks from a given URL using SchemaJsonLD.
Usage: python scripts/dump_schema_org.py <url>
"""
import sys
import re
import json
try:
    from llm_scraper.models.schema import SchemaJsonLD
except ImportError:
    from src.llm_scraper.models.schema import SchemaJsonLD

try:
    import tls_requests
except ImportError:
    tls_requests = None

def fetch_html_tls(url: str) -> str:
    if not tls_requests:
        raise ImportError("tls_requests is not installed.")
    with tls_requests.Client(timeout=20.0, follow_redirects=True) as client:
        r = client.get(url, headers={"User-Agent": "llm-scraper/0.1.0"})
        r.raise_for_status()
        return r.text

def dump_schema_org_from_fixture(fixture_path: str):
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    raw_html = data.get('raw_html')
    if not raw_html:
        url = data.get('url')
        if not url:
            print('No raw_html or url found in fixture.')
            sys.exit(1)
        print(f'Fetching HTML from {url} using tls_requests...')
        raw_html = fetch_html_tls(url)
    # More robust regex for JSON-LD blocks
    ld_blocks = re.findall(r'<script[^>]*type=["\']application/ld\\+json["\'][^>]*>(.*?)</script>', raw_html, re.DOTALL | re.IGNORECASE)
    print(f"Found {len(ld_blocks)} JSON-LD blocks.")
    for i, block in enumerate(ld_blocks, 1):
        print(f"\n--- Block {i} ---")
        try:
            parsed = SchemaJsonLD.parse(block)
            print(parsed.to_json_ld_str())
        except Exception as e:
            print(f"Error parsing block {i}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/dump_schema_org.py <fixture.json>")
        sys.exit(1)
    dump_schema_org_from_fixture(sys.argv[1])
