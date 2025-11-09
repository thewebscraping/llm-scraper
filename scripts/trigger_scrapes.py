#!/usr/bin/env python3
"""
Trigger one-off scraping tasks based on the available parser configs.

This helper is useful when you want to enqueue a scrape wave via cron or manually,
without running Celery Beat. It will:
 - For each config with sitemap_url → enqueue scrape_site_for_rag(mode="sitemap")
 - For each config with rss_url → enqueue scrape_site_for_rag(mode="rss")
 - If neither sitemap nor rss but has follow_urls → enqueue scrape_follow_urls_for_rag(domain)

You can filter by domain using the DOMAIN env or --domain argument.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from celery import Celery


def get_celery() -> Celery:
    # Mirror celery_app.py bootstrap without importing the whole app to avoid side-effects
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    app = Celery("llm_scraper_trigger", broker=redis_url, backend=redis_url)
    return app


def main():
    parser = argparse.ArgumentParser(description="Trigger scraping jobs based on configs")
    parser.add_argument("--domain", help="Only trigger for a specific domain")
    args = parser.parse_args()

    target = (args.domain or os.getenv("DOMAIN") or "").strip().lower() or None
    config_dir = Path(__file__).resolve().parents[1] / "src" / "llm_scraper" / "parsers" / "configs"
    if not config_dir.is_dir():
        print(f"Config dir not found: {config_dir}")
        return 2

    app = get_celery()
    sent = 0

    for cfg in config_dir.rglob("*.json"):
        try:
            data = json.load(open(cfg))
        except Exception as e:
            print(f"Skip {cfg.name}: {e}")
            continue
        domain = (data.get("domain") or "").lower().strip()
        if not domain:
            continue
        if target and target not in {domain, f"www.{domain}"}:
            continue

        # sitemap
        if data.get("sitemap_url"):
            app.send_task(
                "worker.scrape_site_for_rag",
                kwargs={"url": data["sitemap_url"], "mode": "sitemap"},
            )
            print(f"Enqueued sitemap scrape for {domain}")
            sent += 1

        # rss
        if data.get("rss_url"):
            app.send_task(
                "worker.scrape_site_for_rag",
                kwargs={"url": data["rss_url"], "mode": "rss"},
            )
            print(f"Enqueued rss scrape for {domain}")
            sent += 1

        # follow_urls
        if not data.get("sitemap_url") and not data.get("rss_url") and data.get("follow_urls"):
            app.send_task(
                "worker.scrape_follow_urls_for_rag",
                kwargs={"domain": domain},
            )
            print(f"Enqueued follow_urls scrape for {domain}")
            sent += 1

    print(f"Done. Enqueued {sent} tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
