# scrapers/producthunt_scraper.py — Product Hunt scraper

import requests
import time
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

from utils.logger import setup_logger
from utils.helpers import sanitize_text
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

PH_BASE = "https://www.producthunt.com"


def scrape_producthunt() -> list:
    """Scrape Product Hunt for product discussions and complaints."""
    config = get_config()
    platform_config = config["platforms"]["producthunt"]

    if not platform_config.get("enabled", True):
        log.info("Product Hunt scraping disabled")
        return []

    max_items = config["scraper"]["max_items_per_platform"]
    days_back = platform_config.get("days_back", 7)

    all_posts = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        # Fetch recent posts from Product Hunt
        for day_offset in range(days_back):
            if len(all_posts) >= max_items:
                break

            target_date = datetime.now(timezone.utc) - timedelta(days=day_offset)
            date_str = target_date.strftime("%Y/%m/%d")

            url = f"{PH_BASE}/leaderboard/daily/{date_str}/all"
            log.info(f"Fetching Product Hunt for {date_str}...")

            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    log.warning(f"PH returned status {resp.status_code} for {date_str}")
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Find product entries
                product_links = soup.find_all("a", href=re.compile(r"/posts/"))
                seen_slugs = set()

                for link in product_links:
                    if len(all_posts) >= max_items:
                        break

                    href = link.get("href", "")
                    slug = href.split("/posts/")[-1].split("?")[0].split("#")[0]

                    if not slug or slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)

                    ph_id = f"ph_{slug}"
                    if is_already_processed(ph_id):
                        continue

                    # Get product name from the link text
                    title = link.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue

                    # Try to get the tagline from sibling elements
                    parent = link.parent
                    tagline = ""
                    if parent:
                        siblings = parent.find_all(string=True, recursive=True)
                        texts = [t.strip() for t in siblings if t.strip() and t.strip() != title]
                        if texts:
                            tagline = " ".join(texts[:3])

                    all_posts.append({
                        "id": ph_id,
                        "platform": "producthunt",
                        "title": title,
                        "body": tagline or f"Product Hunt product: {title}",
                        "created_utc": target_date.timestamp(),
                        "source": "producthunt",
                        "url": f"{PH_BASE}/posts/{slug}",
                        "type": "post",
                    })

                time.sleep(1)  # Rate limiting

            except Exception as e:
                log.warning(f"Error fetching PH for {date_str}: {e}")
                continue

    except Exception as e:
        log.error(f"Product Hunt scraping error: {e}")

    log.info(f"Product Hunt: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
