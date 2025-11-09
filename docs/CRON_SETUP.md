## System scheduling for scrapers

This project ships with a built-in scheduler using Celery Beat. It auto-discovers parser configs under `src/llm_scraper/parsers/configs/**` and schedules periodic scrapes based on:

- `sitemap_url` → every 6 hours
- `rss_url` → every 15 minutes
- `follow_urls.selector` (when neither sitemap nor RSS are present) → every 30 minutes by default

You can change the follow-URLs cadence with the environment variable:

```
FOLLOW_URLS_INTERVAL_CRON=*/20
```

The scheduler runs inside the `beat` service. For most deployments you do NOT need OS-level cron; just run the worker and beat processes.

### Option A: Docker Compose (recommended)

1) Copy environment template and fill values

```
cp scripts/.env.example .env
```

2) Start Redis, API, Celery worker and Beat

```
docker compose up -d redis worker beat
```

Logs:

```
docker compose logs -f beat worker
```

### Option B: Local processes with Honcho

Install honcho and start all processes using the `Procfile`:

```
pip install honcho
honcho start worker beat
``;

### Option C: macOS launchd (long-running services)

If you prefer macOS-native process management, create two launch agents for the worker and beat. Example `.plist` skeletons:

`~/Library/LaunchAgents/com.llmscraper.worker.plist`

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.llmscraper.worker</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd /path/to/llm_scraper && source .venv/bin/activate && celery -A celery_app.celery_app worker -l info</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>REDIS_URL</key><string>redis://127.0.0.1:6379/0</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/llmscraper-worker.out</string>
  <key>StandardErrorPath</key><string>/tmp/llmscraper-worker.err</string>
</dict>
</plist>
```

`~/Library/LaunchAgents/com.llmscraper.beat.plist` is similar but runs `celery -A celery_app.celery_app beat -l info`.

Load both:

```
launchctl load ~/Library/LaunchAgents/com.llmscraper.worker.plist
launchctl load ~/Library/LaunchAgents/com.llmscraper.beat.plist
```

### Option D: OS cron to trigger one-off runs

Cron is usually not ideal for long-lived processes, but you can use it to trigger one-off scraping waves. This repo includes `scripts/trigger_scrapes.py`, which reads all configs and enqueues Celery tasks for `sitemap_url`/`rss_url` (and `follow_urls` where applicable).

Crontab example (every hour):

```
0 * * * * cd /path/to/llm_scraper && /bin/zsh -lc "source .venv/bin/activate && python scripts/trigger_scrapes.py >> logs/cron_trigger.log 2>&1"
```

### How to add a new site to scheduling

1) Add a parser config JSON under `src/llm_scraper/parsers/configs/<lang>/<initial>/<domain>.json` with any of:
   - `sitemap_url`
   - `rss_url`
   - `follow_urls` (object with `selector`, optional `attribute`, `all`, and optional `discovery_url`)

2) Restart Celery Beat (or it will auto-pick up on next restart). It will create tasks:
   - `scrape_site_for_rag(url=..., mode="sitemap"|"rss")`
   - or `scrape_follow_urls_for_rag(domain=...)` when only `follow_urls` is present.

### Environment knobs

- `FOLLOW_URLS_INTERVAL_CRON` (default `*/30`) minute pattern for follow_urls scheduling
- `FOLLOW_URLS_MAX` (default `25`) cap discovered links per run
- `FOLLOW_URLS_DISCOVERY_TIMEOUT` (default `15`) seconds timeout for discovery fetch
- `MAX_CONCURRENT_SCRAPES` (default `8`) concurrent fetches
- `SCRAPE_TIMEOUT_SECONDS` (default `20`) per-page timeout
- `SCRAPE_RESULT_TTL_DAYS` (default `7`) cache TTL for results/stats
- Vector DB and embedding settings: see `scripts/.env.example`

That’s it — by default, using Docker Compose or Honcho will keep the scheduler and workers running, automatically using your system configs.
