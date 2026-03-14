# scrapers/reddit_scraper.py — Reddit scraper via old.reddit.com JSON (datacenter-friendly)

import requests
import time
import datetime
import random

from utils.logger import setup_logger
from utils.helpers import sanitize_text
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# old.reddit.com is MUCH more datacenter-friendly than www.reddit.com
REDDIT_BASE = "https://old.reddit.com"

# Rotate user-agents to avoid 403s from datacenter IPs
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def _get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


def _fetch_reddit_json(url, retries=3):
    """Fetch JSON from a Reddit URL with retry logic."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=_get_headers(), timeout=15, allow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                return data
            elif resp.status_code == 429:
                wait = 15 * (attempt + 1)
                log.warning(f"Reddit rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
            elif resp.status_code == 403:
                log.warning(f"Reddit 403 for {url} (attempt {attempt+1}). Retrying with new UA...")
                time.sleep(5)
            else:
                log.warning(f"Reddit returned {resp.status_code} for {url}")
                return None
        except Exception as e:
            log.warning(f"Reddit fetch error (attempt {attempt+1}): {e}")
            time.sleep(3)
    return None


def is_post_in_age_range(post_timestamp, min_days, max_days) -> bool:
    post_date = datetime.datetime.fromtimestamp(post_timestamp, tz=datetime.timezone.utc)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - post_date).days
    return min_days <= age_days <= max_days


def fetch_subreddit_posts(subreddit_name, sort="hot", limit=25) -> list:
    """Fetch posts from a subreddit using old.reddit.com JSON endpoint."""
    url = f"{REDDIT_BASE}/r/{subreddit_name}/{sort}.json?limit={limit}&raw_json=1&t=month"

    data = _fetch_reddit_json(url)
    if not data or "data" not in data:
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        if post.get("stickied"):
            continue
        posts.append(post)

    return posts


def scrape_reddit() -> list:
    """Scrape configured subreddits using old.reddit.com JSON. No API key needed."""
    config = get_config()
    platform_config = config["platforms"]["reddit"]

    if not platform_config.get("enabled", True):
        log.info("Reddit scraping disabled")
        return []

    subreddits = platform_config["subreddits"]["primary"]
    max_items = config["scraper"]["max_items_per_platform"]
    min_days = config["scraper"]["min_post_age_days"]
    max_days = config["scraper"]["max_post_age_days"]

    all_posts = []
    seen_ids = set()
    per_subreddit = max(10, max_items // len(subreddits))

    for sub in subreddits:
        log.info(f"Fetching r/{sub} via old.reddit.com JSON...")

        for sort_type in ["hot", "new"]:
            # Rate limit: 3 seconds between requests plus jitter
            time.sleep(3 + random.uniform(0.5, 2.0))

            raw_posts = fetch_subreddit_posts(sub, sort=sort_type, limit=per_subreddit)

            for post in raw_posts:
                reddit_id = post.get("id", "")
                post_id = f"reddit_{reddit_id}"

                if reddit_id in seen_ids:
                    continue
                seen_ids.add(reddit_id)

                created_utc = post.get("created_utc", 0)
                if not is_post_in_age_range(created_utc, min_days, max_days):
                    continue
                if is_already_processed(post_id):
                    continue

                title = post.get("title", "")
                body = post.get("selftext", "")
                permalink = post.get("permalink", "")

                if not title:
                    continue

                # Accept posts with body or link posts
                post_body = body
                if not post_body:
                    ext_url = post.get("url", "")
                    if ext_url:
                        post_body = f"[Link post: {ext_url}]"
                    else:
                        post_body = title  # Use title as body for short posts

                all_posts.append({
                    "id": post_id,
                    "platform": "reddit",
                    "title": title,
                    "body": post_body,
                    "created_utc": created_utc,
                    "source": sub,
                    "url": f"https://www.reddit.com{permalink}",
                    "type": "post",
                })

            log.info(f"  r/{sub}/{sort_type}: {len(raw_posts)} posts fetched")

        if len(all_posts) >= max_items:
            break

    log.info(f"Reddit: Total {len(all_posts)} items scraped (via old.reddit.com)")
    return all_posts[:max_items]
