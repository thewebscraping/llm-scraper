#!/usr/bin/env python3
"""
Validate a JSON fixture against the Article model using Article.from_html.

Usage:
  python scripts/validate_article_fixture.py fixtures/en/c/cointelegraph.com.json
"""
from __future__ import annotations

import sys
import json
import tls_requests
from pathlib import Path
from typing import Any, Dict

from llm_scraper.articles import Article, ArticleCreationError
from llm_scraper.models.selector import ParserConfig
from pydantic import HttpUrl


def load_fixture(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Fixture root must be an object")
        return data
    except Exception as e:
        print(f"❌ Failed to read fixture {path}: {e}")
        raise SystemExit(1)


def fetch_html(url: str) -> str:
    try:
        with tls_requests.Client(timeout=20.0, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "llm-scraper/0.1.0"})
            r.raise_for_status()
            return r.text
    except Exception as e:
        print(f"❌ Failed to fetch URL {url}: {e}")
        raise SystemExit(2)


def load_parser_config(domain: str) -> ParserConfig | None:
    """Load parser config based on domain name."""
    try:
        # Extract first character of domain for directory structure
        first_char = domain.lower()[0]
        config_path = Path(f"src/llm_scraper/parsers/configs/en/{first_char}/{domain}.json")
        if config_path.exists():
            config_data = json.loads(config_path.read_text())
            return ParserConfig.model_validate(config_data)
        return None
    except Exception as e:
        print(f"⚠️ Could not load parser config for {domain}: {e}")
        return None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: validate_article_fixture.py <fixture.json> [--format markdown|html]")
        return 64

    fixture_path = Path(argv[1])
    if not fixture_path.exists():
        print(f"❌ Fixture not found: {fixture_path}")
        return 66
    
    # Parse output format argument
    output_format = "markdown"  # default
    if len(argv) > 2 and argv[2] in ("--format", "-f"):
        if len(argv) > 3 and argv[3] in ("markdown", "html"):
            output_format = argv[3]
        else:
            print("❌ Invalid format. Use 'markdown' or 'html'")
            return 64

    data = load_fixture(fixture_path)
    url = data.get("url")
    domain = data.get("domain")
    if not url:
        print("❌ Missing 'url' field in fixture")
        return 65

    raw_html = data.get("raw_html") or ""
    if not raw_html.strip():
        print("ℹ️ raw_html missing/empty — fetching live HTML...")
        raw_html = fetch_html(url)

    # Load parser config if domain is provided
    parser_config = None
    if domain:
        parser_config = load_parser_config(domain)
        if parser_config:
            print(f"✅ Loaded parser config for {domain}")
            print(f"   - Output format: {output_format}")
            if parser_config.tags:
                print(f"   - Tags selector: {parser_config.tags}")
            if parser_config.topics:
                print(f"   - Topics selector: {parser_config.topics}")
        else:
            print(f"⚠️ No parser config found for {domain}, using default extraction")

    try:
        article = Article.from_html(
            html=raw_html, 
            url=HttpUrl(url), 
            parser_config=parser_config,
            output_format=output_format
        )
    except ArticleCreationError as e:
        print(f"❌ Article creation error: {e}")
        return 70
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Debug: Show parsed data if parser config was used
    if parser_config:
        from llm_scraper.parsers.base import get_parsed_data
        parsed_data = get_parsed_data(raw_html, parser_config, base_url=url)
        print("\n🔍 Debug: Parsed Data")
        print("=" * 50)
        if "tags" in parsed_data:
            print(f"- Tags extracted: {parsed_data['tags']}")
        else:
            print(f"- Tags extracted: None (selector didn't match)")
        if "topics" in parsed_data:
            print(f"- Topics extracted: {parsed_data['topics']}")
        else:
            print(f"- Topics extracted: None (selector didn't match)")
        if "authors" in parsed_data:
            print(f"- Authors extracted: {parsed_data['authors']}")
        if "date_published" in parsed_data:
            print(f"- Date published: {parsed_data['date_published']}")

    # Pretty-formatted output
    print("✅ Article Validated Successfully")
    print("=" * 50)
    print(f"- ID:           {article.id}")
    print(f"- Title:        {article.title}")
    print(f"- Domain:       {article.provenance.domain}")
    print(f"- URL:          {article.provenance.source_url}")
    print(f"- Word Count:   {article.computed_word_count}")
    print(f"- Tokens Est:   {article.computed_token_estimate}")
    print(f"- Chunks:       {len(article.chunks)}")
    print(f"- Created At:   {article.created_at}")

    # Authors section
    if article.authors:
        print("\n👥 Authors")
        print("=" * 50)
        for author in article.authors:
            print(f"- {author.name}")

    # Metadata section
    print("\n📊 Extracted Metadata")
    print("=" * 50)
    print(f"- Language:     {article.metadata.language}")
    print(f"- Published:    {article.metadata.published_at}")
    print(f"- Modified:     {article.metadata.modified_at}")
    
    # Tags and topics if available
    if article.metadata.tags:
        print(f"- Tags:         {article.metadata.tags[:5]}")
    if article.metadata.topics:
        print(f"- Topics:       {article.metadata.topics}")
    
    # Schema.org data if available
    if article.metadata.schema_org:
        import json
        schema_str = json.dumps(article.metadata.schema_org, indent=2, default=str)
        if len(schema_str) > 500:
            schema_str = schema_str[:497] + "..."
        print(f"\n📋 Schema.org Data")
        print("=" * 50)
        print(schema_str)
    
    # Image URL
    if hasattr(article.metadata, 'image_url') and article.metadata.image_url:
        image_url = str(article.metadata.image_url)
        if len(image_url) > 50:
            image_url = image_url[:47] + "..."
        print(f"- Image URL:    {image_url}")
    
    # Description
    if hasattr(article, 'description') and article.description:
        desc = str(article.description)
        if len(desc) > 80:
            desc = desc[:77] + "..."
        print(f"- Description:  {desc}")

    # Content body preview (5-10 words from start and end)
    if article.content:
        print(f"\n📄 Content Body Preview")
        print("=" * 50)
        
        # Get full content
        content = article.content
        words = content.split()
        total_words = len(words)
        
        # Show first 10 words
        first_words = ' '.join(words[:10]) if len(words) >= 10 else ' '.join(words)
        
        # Show last 10 words
        last_words = ' '.join(words[-10:]) if len(words) >= 10 else ''
        
        print(f"- Total words:  {total_words}")
        print(f"- First 10:     {first_words}...")
        if last_words:
            print(f"- Last 10:      ...{last_words}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
