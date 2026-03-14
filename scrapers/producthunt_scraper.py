# scrapers/producthunt_scraper.py — Product Hunt scraper using public Atom feed

import requests
import time
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html import unescape

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# The Atom feed is the only PH endpoint that reliably works without auth.
# GraphQL and HTML pages return 403 from most IPs.
PH_FEED_URL = "https://www.producthunt.com/feed"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


def _strip_html(text):
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = unescape(clean)
    return " ".join(clean.split()).strip()


def _parse_feed(feed_text) -> list:
    """Parse the Atom feed XML and extract product entries."""
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError as e:
        log.error(f"PH feed XML parse error: {e}")
        return []

    entries = root.findall("atom:entry", ATOM_NS)
    products = []

    for entry in entries:
        title_el = entry.find("atom:title", ATOM_NS)
        link_el = entry.find("atom:link", ATOM_NS)
        content_el = entry.find("atom:content", ATOM_NS)
        updated_el = entry.find("atom:updated", ATOM_NS)
        id_el = entry.find("atom:id", ATOM_NS)

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.get("href", "") if link_el is not None else ""
        content_html = content_el.text if content_el is not None and content_el.text else ""
        updated = updated_el.text if updated_el is not None and updated_el.text else ""
        entry_id = id_el.text if id_el is not None and id_el.text else ""

        if not title:
            continue

        # Extract tagline from content (first <p> tag typically)
        content_text = _strip_html(content_html)

        # Derive slug from link or ID
        slug = ""
        if link:
            parts = link.rstrip("/").split("/")
            slug = parts[-1] if parts else ""
        if not slug and entry_id:
            slug = entry_id.split("/")[-1].split(":")[-1]

        products.append({
            "title": title,
            "slug": slug,
            "content": content_text,
            "url": link,
            "updated": updated,
        })

    return products


def scrape_producthunt() -> list:
    """Scrape Product Hunt using the public Atom feed."""
    config = get_config()
    platform_config = config["platforms"]["producthunt"]

    if not platform_config.get("enabled", True):
        log.info("Product Hunt scraping disabled")
        return []

    max_items = config["scraper"]["max_items_per_platform"]

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/atom+xml, application/xml, text/xml, */*",
    }

    all_posts = []

    try:
        log.info("Fetching Product Hunt Atom feed...")
        resp = requests.get(PH_FEED_URL, headers=headers, timeout=15)

        if resp.status_code != 200:
            log.warning(f"PH feed returned {resp.status_code}")
            return []

        products = _parse_feed(resp.text)
        log.info(f"PH feed: {len(products)} products found")

        for product in products:
            if len(all_posts) >= max_items:
                break

            slug = product.get("slug", "")
            if not slug:
                continue

            ph_id = f"ph_{slug}"
            if is_already_processed(ph_id):
                continue

            title = product.get("title", "")
            content = product.get("content", "")
            url = product.get("url", f"https://www.producthunt.com/posts/{slug}")

            if not title or len(title) < 2:
                continue

            # Parse the updated timestamp
            updated = product.get("updated", "")
            try:
                created_utc = datetime.fromisoformat(
                    updated.replace("Z", "+00:00")
                ).timestamp()
            except Exception:
                created_utc = datetime.now(timezone.utc).timestamp()

            all_posts.append({
                "id": ph_id,
                "platform": "producthunt",
                "title": title,
                "body": content or f"Product Hunt: {title}",
                "created_utc": created_utc,
                "source": "producthunt",
                "url": url,
                "type": "post",
            })

    except Exception as e:
        log.error(f"Product Hunt scraping error: {e}")

    log.info(f"Product Hunt: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
