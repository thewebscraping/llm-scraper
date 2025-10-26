from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, List
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from .models.selector import ParserConfig


def find_sitemaps_from_robots(robots_txt_content: str, base_url: str) -> List[str]:
    """
    Parses a robots.txt file content to find sitemap URLs.
    """
    sitemaps = []
    for line in robots_txt_content.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemap_url = line.split(":", 1)[1].strip()
            # Ensure the sitemap URL is absolute
            sitemaps.append(urljoin(base_url, sitemap_url))
    return sitemaps


def parse_sitemap(sitemap_content: bytes) -> List[str]:
    """
    Parses the content of a sitemap.xml file (or a gzipped one) and returns a list of URLs.
    """
    urls = []
    try:
        # Handle gzipped sitemaps
        if sitemap_content.startswith(b"\x1f\x8b"):
            sitemap_content = gzip.decompress(sitemap_content)

        root = ET.fromstring(sitemap_content)
        # XML namespace is often present and needs to be handled
        namespace = {"ns": root.tag.split("}")[0][1:]} if "}" in root.tag else {"ns": ""}

        # Find all <loc> tags, which contain the URLs
        for loc in root.findall(".//ns:loc", namespace):
            if loc.text:
                urls.append(loc.text.strip())
    except ET.ParseError:
        # The sitemap might be a sitemap index file, so we parse it differently
        try:
            root = ET.fromstring(sitemap_content)
            namespace = {"ns": root.tag.split("}")[0][1:]} if "}" in root.tag else {"ns": ""}
            for sitemap in root.findall(".//ns:sitemap/ns:loc", namespace):
                if sitemap.text:
                    # This is a URL to another sitemap, not a final article URL
                    # For simplicity, we'll treat them as discoverable URLs for now.
                    # A more robust implementation might recursively fetch these.
                    urls.append(sitemap.text.strip())
        except ET.ParseError:
            # Ignore sitemaps that are not well-formed XML
            pass
    return urls


def find_rss_feeds(html_content: str, base_url: str) -> List[str]:
    """
    Finds RSS feed links from the <head> section of an HTML document.
    """
    soup = BeautifulSoup(html_content, "lxml")
    feeds = []
    # Look for <link> tags with type="application/rss+xml" or "application/atom+xml"
    for link in soup.find_all("link", attrs={"type": ["application/rss+xml", "application/atom+xml"]}):
        href = link.get("href")
        if href:
            # Ensure the feed URL is absolute
            feeds.append(urljoin(base_url, href))
    return feeds


def parse_rss_feed(feed_content: bytes) -> List[str]:
    """
    Parses the content of an RSS or Atom feed and returns a list of article URLs.
    """
    urls = []
    try:
        root = ET.fromstring(feed_content)
        # Find all <link> tags within <item> (for RSS) or <entry> (for Atom)
        for item in root.findall(".//item/link") + root.findall(".//{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}link"):
            url = item.text or item.get("href")
            if url:
                urls.append(url.strip())
    except ET.ParseError:
        # Ignore feeds that are not well-formed XML
        pass
    return urls


async def discover_urls(
    domain: str,
    parser_config: "ParserConfig",
    user_agent: str = "llm-scraper/1.0",
) -> List[str]:
    """
    High-level function to discover all possible article URLs from a domain.
    It prioritizes manual lists from the parser_config and falls back to
    automatic discovery (robots.txt, sitemaps, and RSS feeds).
    """
    base_url = f"https://{domain}"
    urls = set()
    headers = {"User-Agent": user_agent}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        # 1. Prioritize manual lists from the config
        manual_sitemaps = parser_config.manual_sitemaps
        manual_rss_feeds = parser_config.manual_rss_feeds

        if manual_sitemaps:
            for sitemap_url in manual_sitemaps:
                try:
                    sitemap_response = await client.get(sitemap_url)
                    if sitemap_response.status_code == 200:
                        for url in parse_sitemap(sitemap_response.content):
                            urls.add(url)
                except httpx.RequestError:
                    continue  # Ignore failed manual sitemap fetches

        if manual_rss_feeds:
            for feed_url in manual_rss_feeds:
                try:
                    feed_response = await client.get(feed_url)
                    if feed_response.status_code == 200:
                        for url in parse_rss_feed(feed_response.content):
                            urls.add(url)
                except httpx.RequestError:
                    continue  # Ignore failed manual feed fetches

        # If manual URLs were found, we can return them immediately.
        # This gives you precise control.
        if urls:
            return list(urls)

        # 2. Automatic discovery: Check robots.txt for sitemaps
        try:
            robots_url = urljoin(base_url, "/robots.txt")
            response = await client.get(robots_url)
            if response.status_code == 200:
                sitemap_urls = find_sitemaps_from_robots(response.text, base_url)
                for sitemap_url in sitemap_urls:
                    try:
                        sitemap_response = await client.get(sitemap_url)
                        if sitemap_response.status_code == 200:
                            for url in parse_sitemap(sitemap_response.content):
                                urls.add(url)
                    except httpx.RequestError:
                        continue
        except httpx.RequestError:
            pass  # robots.txt might not exist

        # 3. Automatic discovery: Check homepage for RSS feeds
        try:
            response = await client.get(base_url)
            if response.status_code == 200:
                rss_feed_urls = find_rss_feeds(response.text, base_url)
                for feed_url in rss_feed_urls:
                    try:
                        feed_response = await client.get(feed_url)
                        if feed_response.status_code == 200:
                            for url in parse_rss_feed(feed_response.content):
                                urls.add(url)
                    except httpx.RequestError:
                        continue
        except httpx.RequestError:
            pass  # Homepage might be down

    return list(urls)
