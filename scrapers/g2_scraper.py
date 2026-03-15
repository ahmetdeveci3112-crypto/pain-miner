# scrapers/g2_scraper.py — G2 reviews scraper via HTML parsing (low-star reviews = pain points)

import requests
import time
import random
import re
import hashlib
from datetime import datetime, timezone
from html import unescape

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# G2 category pages with reviews sorted by lowest rating
G2_REVIEWS_URL = "https://www.g2.com/categories/{category}#reviews"
G2_PRODUCT_REVIEWS_URL = "https://www.g2.com/products/{product}/reviews?order=most_recent&filters%5Bstar_rating%5D=1"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# G2 popular software category slugs for review mining
DEFAULT_CATEGORIES = [
    "project-management",
    "crm",
    "marketing-automation",
    "accounting",
    "help-desk",
    "email-marketing",
    "hr-management",
    "social-media-management",
]


def _strip_html(html_text):
    """Remove HTML tags and decode entities."""
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = unescape(clean)
    return " ".join(clean.split()).strip()


def _extract_reviews_from_html(html_text, category) -> list:
    """Extract review snippets from G2 HTML page."""
    reviews = []

    # Look for review titles and bodies (G2 uses structured patterns)
    # Pattern: "What do you dislike" sections contain pain points
    dislike_pattern = re.compile(
        r'(?:What do you dislike|What I dislike|I don\'t like|Cons|Dislikes?).*?'
        r'(?:<p[^>]*>|<div[^>]*>)(.*?)(?:</p>|</div>)',
        re.IGNORECASE | re.DOTALL
    )

    # Also try to find review card patterns
    review_pattern = re.compile(
        r'<div[^>]*class="[^"]*review[^"]*"[^>]*>.*?'
        r'<h[2-4][^>]*>(.*?)</h[2-4]>.*?'
        r'(?:<p[^>]*>|<div[^>]*>)(.*?)(?:</p>|</div>)',
        re.IGNORECASE | re.DOTALL
    )

    # Extract any review snippets we can find
    for match in review_pattern.finditer(html_text):
        title = _strip_html(match.group(1))
        body = _strip_html(match.group(2))
        if title and len(title) > 5:
            reviews.append({"title": title, "body": body})

    # Also look for meta description or structured data
    meta_desc = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html_text)
    if meta_desc and not reviews:
        desc = _strip_html(meta_desc.group(1))
        if desc:
            reviews.append({
                "title": f"G2 {category} Reviews",
                "body": desc,
            })

    # Extract any visible review text blocks
    text_blocks = re.findall(
        r'<div[^>]*data-.*?review.*?>(.*?)</div>',
        html_text, re.IGNORECASE | re.DOTALL
    )
    for block in text_blocks[:10]:
        text = _strip_html(block)
        if text and len(text) > 30 and len(text) < 2000:
            reviews.append({
                "title": f"G2 Review: {category}",
                "body": text,
            })

    return reviews


def scrape_g2() -> list:
    """Scrape G2 for low-star reviews as pain points."""
    config = get_config()
    platform_config = config["platforms"].get("g2", {})

    if not platform_config.get("enabled", False):
        log.info("G2 scraping disabled")
        return []

    max_items = config["scraper"]["max_items_per_platform"]
    categories = platform_config.get("categories", DEFAULT_CATEGORIES)

    all_posts = []
    seen_ids = set()

    log.info(f"G2: Scraping reviews from {len(categories)} categories...")

    for i, category in enumerate(categories):
        if len(all_posts) >= max_items:
            break

        url = G2_REVIEWS_URL.format(category=category)
        log.info(f"  G2 category ({i+1}/{len(categories)}): {category}")

        # Rate limit: 8-12s between requests (be gentle with G2)
        if i > 0:
            time.sleep(8 + random.uniform(2.0, 4.0))

        try:
            resp = requests.get(url, headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
            }, timeout=20, allow_redirects=True)

            if resp.status_code == 403:
                log.warning(f"G2 returned 403 (Cloudflare blocked) for {category}")
                continue
            elif resp.status_code != 200:
                log.warning(f"G2 returned {resp.status_code} for {category}")
                continue

            reviews = _extract_reviews_from_html(resp.text, category)
            log.info(f"    {len(reviews)} review snippets found")

            for review in reviews:
                if len(all_posts) >= max_items:
                    break

                title = review.get("title", "").strip()
                body = review.get("body", "").strip()

                if not title or not body or len(body) < 15:
                    continue

                g2_hash = hashlib.md5(f"{title}_{body[:100]}".encode()).hexdigest()[:12]
                post_id = f"g2_{g2_hash}"

                if g2_hash in seen_ids:
                    continue
                seen_ids.add(g2_hash)

                if is_already_processed(post_id):
                    continue

                all_posts.append({
                    "id": post_id,
                    "platform": "g2",
                    "title": title,
                    "body": body[:2000],
                    "created_utc": datetime.now(timezone.utc).timestamp(),
                    "source": category,
                    "url": url,
                    "type": "review",
                })

        except Exception as e:
            log.error(f"G2 scraping error for {category}: {e}")

    log.info(f"G2: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
