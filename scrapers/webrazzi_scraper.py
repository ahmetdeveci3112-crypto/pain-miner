# scrapers/webrazzi_scraper.py — Webrazzi (Turkish tech/startup news) via RSS

import requests
import time
import random
import re
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# Webrazzi — Turkish tech startup news
WEBRAZZI_FEED = "https://webrazzi.com/feed/"

# ShiftDelete — Turkish tech news / reviews
SHIFTDELETE_FEED = "https://shiftdelete.net/feed"

# Donanım Haber — Turkish hardware/tech news
DONANIMHABER_FEED = "https://www.donanimhaber.com/rss/tum/"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
]


def _strip_html(html_text):
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = unescape(clean)
    return " ".join(clean.split()).strip()


def _parse_rss(feed_text, platform) -> list:
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError as e:
        log.error(f"{platform} RSS parse error: {e}")
        return []

    entries = []
    channel = root.find("channel")
    if channel is None:
        return entries

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()

        # Try content:encoded first, then description
        content_encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
        desc = item.findtext("description") or ""
        body = _strip_html(content_encoded or desc)

        pub_date = (item.findtext("pubDate") or "").strip()
        guid = (item.findtext("guid") or link).strip()

        if title and len(title) > 5:
            entries.append({
                "title": title, "url": link, "body": body,
                "pub_date": pub_date, "guid": guid,
            })

    return entries


def scrape_webrazzi() -> list:
    """Scrape Webrazzi, ShiftDelete, and DonanımHaber RSS feeds."""
    config = get_config()
    platform_config = config["platforms"].get("webrazzi", {})

    if not platform_config.get("enabled", False):
        log.info("Turkish news scraping disabled")
        return []

    max_items = config["scraper"]["max_items_per_platform"]

    feeds = [
        ("webrazzi", WEBRAZZI_FEED),
        ("shiftdelete", SHIFTDELETE_FEED),
        ("donanimhaber", DONANIMHABER_FEED),
    ]

    all_posts = []
    seen_ids = set()

    log.info("Turkish News: Fetching RSS feeds (Webrazzi, ShiftDelete, DonanımHaber)...")

    for i, (source_name, feed_url) in enumerate(feeds):
        if len(all_posts) >= max_items:
            break

        log.info(f"  {source_name}: fetching RSS...")

        if i > 0:
            time.sleep(2 + random.uniform(0.5, 1.0))

        try:
            resp = requests.get(feed_url, headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            }, timeout=15)

            if resp.status_code != 200:
                log.warning(f"{source_name} RSS returned {resp.status_code}")
                continue

            entries = _parse_rss(resp.text, source_name)
            log.info(f"    {len(entries)} entries")

            for entry in entries:
                if len(all_posts) >= max_items:
                    break

                wr_hash = hashlib.md5(entry["guid"].encode()).hexdigest()[:12]
                post_id = f"webrazzi_{wr_hash}"

                if wr_hash in seen_ids or is_already_processed(post_id):
                    continue
                seen_ids.add(wr_hash)

                title = entry["title"]
                body = entry.get("body", "")

                try:
                    from email.utils import parsedate_to_datetime
                    created_utc = parsedate_to_datetime(entry["pub_date"]).timestamp()
                except Exception:
                    created_utc = datetime.now(timezone.utc).timestamp()

                all_posts.append({
                    "id": post_id,
                    "platform": "webrazzi",
                    "title": title,
                    "body": body if body and len(body) > 10 else title,
                    "created_utc": created_utc,
                    "source": source_name,
                    "url": entry["url"],
                    "type": "article",
                })

        except Exception as e:
            log.error(f"{source_name} error: {e}")

    log.info(f"Turkish News: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
