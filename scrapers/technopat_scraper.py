# scrapers/technopat_scraper.py — Technopat Forum scraper via RSS feeds

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

# Technopat Forum RSS — each section has an RSS feed at /index.rss
TECHNOPAT_SECTIONS = {
    # Yazılım & Teknoloji sorunları — pain point kaynağı
    "yazilim-sorunlari": "https://www.technopat.net/sosyal/bolum/yazilim-ve-donanim-sorunlari.pair-teknoloji.56/index.rss",
    "mobil-sorunlar": "https://www.technopat.net/sosyal/bolum/mobil-cihaz-sorunlari.pair-sosyal.101/index.rss",
    "internet-sorunlari": "https://www.technopat.net/sosyal/bolum/internet-network.pair-teknoloji.94/index.rss",
    "uygulama-onerileri": "https://www.technopat.net/sosyal/bolum/yazilim-uygulamalar.pair-teknoloji.64/index.rss",
    "proje-gelistirme": "https://www.technopat.net/sosyal/bolum/web-yazilim-gelistirme.pair-teknoloji.30/index.rss",
}

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


def _parse_rss(feed_text) -> list:
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError as e:
        log.error(f"Technopat RSS parse error: {e}")
        return []

    entries = []
    channel = root.find("channel")
    if channel is None:
        return entries

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = _strip_html(item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or item.findtext("description") or "")
        pub_date = (item.findtext("pubDate") or "").strip()
        guid = (item.findtext("guid") or link).strip()

        if title and len(title) > 5:
            entries.append({
                "title": title, "url": link, "body": desc,
                "pub_date": pub_date, "guid": guid,
            })

    return entries


def scrape_technopat() -> list:
    config = get_config()
    platform_config = config["platforms"].get("technopat", {})

    if not platform_config.get("enabled", False):
        log.info("Technopat scraping disabled")
        return []

    max_items = config["scraper"]["max_items_per_platform"]
    all_posts = []
    seen_ids = set()

    log.info(f"Technopat: Fetching {len(TECHNOPAT_SECTIONS)} forum sections...")

    for i, (section_name, url) in enumerate(TECHNOPAT_SECTIONS.items()):
        if len(all_posts) >= max_items:
            break

        log.info(f"  Technopat ({i+1}/{len(TECHNOPAT_SECTIONS)}): {section_name}")

        if i > 0:
            time.sleep(3 + random.uniform(0.5, 1.5))

        try:
            resp = requests.get(url, headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            }, timeout=15)

            if resp.status_code != 200:
                log.warning(f"Technopat RSS returned {resp.status_code} for {section_name}")
                continue

            entries = _parse_rss(resp.text)
            log.info(f"    {len(entries)} entries")

            for entry in entries:
                if len(all_posts) >= max_items:
                    break

                tp_hash = hashlib.md5(entry["guid"].encode()).hexdigest()[:12]
                post_id = f"technopat_{tp_hash}"

                if tp_hash in seen_ids or is_already_processed(post_id):
                    continue
                seen_ids.add(tp_hash)

                title = entry["title"]
                body = entry.get("body", "")

                try:
                    from email.utils import parsedate_to_datetime
                    created_utc = parsedate_to_datetime(entry["pub_date"]).timestamp()
                except Exception:
                    created_utc = datetime.now(timezone.utc).timestamp()

                all_posts.append({
                    "id": post_id,
                    "platform": "technopat",
                    "title": title,
                    "body": body if body and len(body) > 10 else title,
                    "created_utc": created_utc,
                    "source": section_name,
                    "url": entry["url"],
                    "type": "post",
                })

        except Exception as e:
            log.error(f"Technopat error for {section_name}: {e}")

    log.info(f"Technopat: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
