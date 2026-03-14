# scrapers/reddit_scraper.py — Reddit scraper via RSS feeds (NO API key, works from datacenters)

import requests
import time
import datetime
import random
import re
import xml.etree.ElementTree as ET
from html import unescape

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# Reddit RSS feeds work from both residential AND datacenter IPs.
# No API key, no OAuth, no CAPTCHA — just plain Atom/RSS.
REDDIT_RSS = "https://www.reddit.com/r/{subreddit}/{sort}/.rss?limit=25"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def _strip_html(html_text):
    """Remove HTML tags and decode entities."""
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = unescape(clean)
    return " ".join(clean.split()).strip()


def _fetch_rss(subreddit, sort="hot", retries=3):
    """Fetch RSS feed for a subreddit."""
    url = REDDIT_RSS.format(subreddit=subreddit, sort=sort)

    for attempt in range(retries):
        try:
            resp = requests.get(url, headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*",
            }, timeout=15)

            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log.warning(f"Reddit RSS rate limited. Waiting {wait}s...")
                time.sleep(wait)
            elif resp.status_code == 403:
                log.warning(f"Reddit RSS 403 for r/{subreddit}/{sort} (attempt {attempt+1})")
                time.sleep(5)
            else:
                log.warning(f"Reddit RSS returned {resp.status_code} for r/{subreddit}/{sort}")
                return None
        except Exception as e:
            log.warning(f"Reddit RSS error (attempt {attempt+1}): {e}")
            time.sleep(3)

    return None


def _parse_rss_entries(xml_text, subreddit) -> list:
    """Parse Atom/RSS feed and extract posts."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.error(f"RSS parse error for r/{subreddit}: {e}")
        return []

    entries = root.findall("atom:entry", ATOM_NS)
    posts = []

    for entry in entries:
        id_el = entry.find("atom:id", ATOM_NS)
        title_el = entry.find("atom:title", ATOM_NS)
        link_el = entry.find("atom:link", ATOM_NS)
        content_el = entry.find("atom:content", ATOM_NS)
        updated_el = entry.find("atom:updated", ATOM_NS)

        # Extract Reddit post ID from the entry ID (format: t3_xxxxx)
        entry_id = id_el.text if id_el is not None and id_el.text else ""
        reddit_id = entry_id.replace("t3_", "") if entry_id.startswith("t3_") else entry_id

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.get("href", "") if link_el is not None else ""
        content_html = content_el.text if content_el is not None and content_el.text else ""
        updated = updated_el.text if updated_el is not None and updated_el.text else ""

        if not title or not reddit_id:
            continue

        # Clean HTML content to get plain text body
        body = _strip_html(content_html)

        # Parse date
        try:
            created_utc = datetime.datetime.fromisoformat(
                updated.replace("Z", "+00:00")
            ).timestamp()
        except Exception:
            created_utc = datetime.datetime.now(datetime.timezone.utc).timestamp()

        posts.append({
            "reddit_id": reddit_id,
            "title": title,
            "body": body,
            "url": link,
            "created_utc": created_utc,
        })

    return posts


def is_post_in_age_range(post_timestamp, min_days, max_days) -> bool:
    post_date = datetime.datetime.fromtimestamp(post_timestamp, tz=datetime.timezone.utc)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - post_date).days
    return min_days <= age_days <= max_days


def scrape_reddit() -> list:
    """Scrape subreddits using RSS feeds. No API key needed. Works from datacenters."""
    config = get_config()
    platform_config = config["platforms"]["reddit"]

    if not platform_config.get("enabled", True):
        log.info("Reddit scraping disabled")
        return []

    log.info("Reddit: Using RSS feeds (no API key needed)")

    subreddits = platform_config["subreddits"]["primary"]
    max_items = config["scraper"]["max_items_per_platform"]
    min_days = config["scraper"]["min_post_age_days"]
    max_days = config["scraper"]["max_post_age_days"]

    all_posts = []
    seen_ids = set()

    for sub in subreddits:
        if len(all_posts) >= max_items:
            break

        log.info(f"Fetching r/{sub} RSS feed...")

        for sort_type in ["hot", "new"]:
            # Rate limit: 3 seconds + jitter between requests
            time.sleep(3 + random.uniform(0.5, 2.0))

            xml_text = _fetch_rss(sub, sort=sort_type)
            if not xml_text:
                continue

            entries = _parse_rss_entries(xml_text, sub)

            for entry in entries:
                reddit_id = entry["reddit_id"]
                post_id = f"reddit_{reddit_id}"

                if reddit_id in seen_ids:
                    continue
                seen_ids.add(reddit_id)

                if not is_post_in_age_range(entry["created_utc"], min_days, max_days):
                    continue
                if is_already_processed(post_id):
                    continue

                body = entry["body"]
                if not body or len(body) < 10:
                    body = entry["title"]  # Use title as body for short/link posts

                all_posts.append({
                    "id": post_id,
                    "platform": "reddit",
                    "title": entry["title"],
                    "body": body,
                    "created_utc": entry["created_utc"],
                    "source": sub,
                    "url": entry["url"],
                    "type": "post",
                })

            log.info(f"  r/{sub}/{sort_type}: {len(entries)} entries")

    log.info(f"Reddit: Total {len(all_posts)} items scraped (via RSS)")
    return all_posts[:max_items]
