# scrapers/indiehackers_scraper.py — Indie Hackers scraper via unofficial RSS (ihrss.io)

import requests
import time
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# Unofficial RSS feeds for Indie Hackers via ihrss.io
IH_FEEDS = [
    "https://ihrss.io/api/feed",                    # Homepage / latest
    "https://ihrss.io/api/feed?group=growth",        # Growth discussions
    "https://ihrss.io/api/feed?group=building-in-public",  # Building in Public
]

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
RSS_NS = {}  # Standard RSS has no namespace

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
]


def _strip_html(html_text):
    """Remove HTML tags and decode entities."""
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = unescape(clean)
    return " ".join(clean.split()).strip()


def _parse_feed(feed_text) -> list:
    """Parse RSS/Atom feed and extract entries."""
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError as e:
        log.error(f"IH feed XML parse error: {e}")
        return []

    entries = []

    # Try Atom format first
    atom_entries = root.findall("atom:entry", ATOM_NS)
    if atom_entries:
        for entry in atom_entries:
            title_el = entry.find("atom:title", ATOM_NS)
            link_el = entry.find("atom:link", ATOM_NS)
            content_el = entry.find("atom:content", ATOM_NS)
            summary_el = entry.find("atom:summary", ATOM_NS)
            updated_el = entry.find("atom:updated", ATOM_NS)
            id_el = entry.find("atom:id", ATOM_NS)

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            link = link_el.get("href", "") if link_el is not None else ""
            content = ""
            if content_el is not None and content_el.text:
                content = _strip_html(content_el.text)
            elif summary_el is not None and summary_el.text:
                content = _strip_html(summary_el.text)
            updated = updated_el.text if updated_el is not None and updated_el.text else ""
            entry_id = id_el.text if id_el is not None and id_el.text else link

            if title:
                entries.append({
                    "title": title, "url": link, "body": content,
                    "updated": updated, "entry_id": entry_id,
                })
        return entries

    # Try standard RSS format
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            desc = _strip_html(item.findtext("description", ""))
            content = _strip_html(item.findtext("content:encoded", "") or "")
            pub_date = item.findtext("pubDate", "")
            guid = item.findtext("guid", link)

            if title:
                entries.append({
                    "title": title, "url": link,
                    "body": content or desc,
                    "updated": pub_date, "entry_id": guid,
                })

    return entries


def scrape_indiehackers() -> list:
    """Scrape Indie Hackers using unofficial RSS feeds."""
    config = get_config()
    platform_config = config["platforms"].get("indiehackers", {})

    if not platform_config.get("enabled", False):
        log.info("Indie Hackers scraping disabled")
        return []

    max_items = config["scraper"]["max_items_per_platform"]
    all_posts = []
    seen_ids = set()

    log.info("Indie Hackers: Fetching RSS feeds...")

    for feed_url in IH_FEEDS:
        if len(all_posts) >= max_items:
            break

        try:
            time.sleep(3 + random.uniform(0.5, 1.5))

            resp = requests.get(feed_url, headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            }, timeout=15)

            if resp.status_code != 200:
                log.warning(f"IH feed returned {resp.status_code}: {feed_url}")
                continue

            entries = _parse_feed(resp.text)
            log.info(f"  IH feed: {len(entries)} entries from {feed_url.split('?')[-1]}")

            for entry in entries:
                if len(all_posts) >= max_items:
                    break

                entry_id = entry.get("entry_id", "")
                # Create a stable ID from the URL or entry_id
                import hashlib
                ih_hash = hashlib.md5(entry_id.encode()).hexdigest()[:12]
                post_id = f"ih_{ih_hash}"

                if ih_hash in seen_ids:
                    continue
                seen_ids.add(ih_hash)

                if is_already_processed(post_id):
                    continue

                title = entry.get("title", "").strip()
                body = entry.get("body", "")
                url = entry.get("url", "")

                if not title or len(title) < 5:
                    continue

                # Parse date
                updated = entry.get("updated", "")
                try:
                    created_utc = datetime.fromisoformat(
                        updated.replace("Z", "+00:00")
                    ).timestamp()
                except Exception:
                    created_utc = datetime.now(timezone.utc).timestamp()

                all_posts.append({
                    "id": post_id,
                    "platform": "indiehackers",
                    "title": title,
                    "body": body if body and len(body) > 10 else title,
                    "created_utc": created_utc,
                    "source": "indiehackers",
                    "url": url,
                    "type": "post",
                })

        except Exception as e:
            log.error(f"IH scraping error for {feed_url}: {e}")

    log.info(f"Indie Hackers: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
