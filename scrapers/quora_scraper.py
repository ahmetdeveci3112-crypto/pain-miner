# scrapers/quora_scraper.py — Quora scraper via topic RSS feeds

import requests
import time
import random
import re
import xml.etree.ElementTree as ET
import hashlib
from datetime import datetime, timezone
from html import unescape

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# Quora supports RSS feeds by appending /rss to topic URLs
QUORA_TOPIC_RSS = "https://www.quora.com/topic/{topic}/rss"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

# Default topics related to pain points & software needs
DEFAULT_TOPICS = [
    "SaaS",
    "Startups",
    "Software-Development",
    "Productivity-Tools",
    "Web-Applications",
    "Entrepreneurship",
    "Small-Business",
    "Project-Management",
    "Automation",
    "Freelancing",
]


def _strip_html(html_text):
    """Remove HTML tags and decode entities."""
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = unescape(clean)
    return " ".join(clean.split()).strip()


def _parse_rss(feed_text, topic) -> list:
    """Parse Quora RSS feed."""
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError as e:
        log.error(f"Quora RSS parse error for {topic}: {e}")
        return []

    entries = []
    channel = root.find("channel")
    if channel is None:
        return entries

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = _strip_html(item.findtext("description") or "")
        pub_date = (item.findtext("pubDate") or "").strip()
        guid = (item.findtext("guid") or link).strip()

        if title:
            entries.append({
                "title": title,
                "url": link,
                "body": desc,
                "pub_date": pub_date,
                "guid": guid,
            })

    return entries


def scrape_quora() -> list:
    """Scrape Quora topic RSS feeds for pain points."""
    config = get_config()
    platform_config = config["platforms"].get("quora", {})

    if not platform_config.get("enabled", False):
        log.info("Quora scraping disabled")
        return []

    max_items = config["scraper"]["max_items_per_platform"]
    topics = platform_config.get("topics", DEFAULT_TOPICS)

    all_posts = []
    seen_ids = set()

    log.info(f"Quora: Fetching RSS for {len(topics)} topics...")

    for i, topic in enumerate(topics):
        if len(all_posts) >= max_items:
            break

        url = QUORA_TOPIC_RSS.format(topic=topic)
        log.info(f"  Quora topic ({i+1}/{len(topics)}): {topic}")

        # Rate limit: 5-8s between requests
        if i > 0:
            time.sleep(5 + random.uniform(1.0, 3.0))

        try:
            resp = requests.get(url, headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            }, timeout=15)

            if resp.status_code != 200:
                log.warning(f"Quora RSS returned {resp.status_code} for {topic}")
                continue

            entries = _parse_rss(resp.text, topic)
            log.info(f"    {len(entries)} entries found")

            for entry in entries:
                if len(all_posts) >= max_items:
                    break

                guid = entry.get("guid", "")
                q_hash = hashlib.md5(guid.encode()).hexdigest()[:12]
                post_id = f"quora_{q_hash}"

                if q_hash in seen_ids:
                    continue
                seen_ids.add(q_hash)

                if is_already_processed(post_id):
                    continue

                title = entry.get("title", "").strip()
                body = entry.get("body", "")

                if not title or len(title) < 5:
                    continue

                # Parse pub date
                try:
                    from email.utils import parsedate_to_datetime
                    created_utc = parsedate_to_datetime(entry["pub_date"]).timestamp()
                except Exception:
                    created_utc = datetime.now(timezone.utc).timestamp()

                all_posts.append({
                    "id": post_id,
                    "platform": "quora",
                    "title": title,
                    "body": body if body and len(body) > 10 else title,
                    "created_utc": created_utc,
                    "source": topic,
                    "url": entry.get("url", ""),
                    "type": "question",
                })

        except Exception as e:
            log.error(f"Quora scraping error for {topic}: {e}")

    log.info(f"Quora: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
