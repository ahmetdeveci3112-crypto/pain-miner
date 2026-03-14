# scrapers/reddit_scraper.py — Reddit scraper via public JSON endpoints (NO API key needed)

import requests
import time
import datetime

from utils.logger import setup_logger
from utils.helpers import sanitize_text
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

REDDIT_BASE = "https://www.reddit.com"
HEADERS = {
    "User-Agent": "PainMiner/2.0 (research bot; +https://github.com/pain-miner)",
    "Accept": "application/json",
}


def _fetch_reddit_json(url, retries=3):
    """Fetch JSON from a Reddit URL with retry logic."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log.warning(f"Reddit rate limited. Waiting {wait}s...")
                time.sleep(wait)
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


def fetch_subreddit_posts(subreddit_name, sort="hot", limit=25, after=None) -> list:
    """Fetch posts from a subreddit using the public JSON endpoint."""
    url = f"{REDDIT_BASE}/r/{subreddit_name}/{sort}.json?limit={limit}&raw_json=1"
    if after:
        url += f"&after={after}"

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
    """Scrape configured subreddits using public JSON endpoints. No API key needed."""
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
        log.info(f"Fetching r/{sub} via JSON endpoint...")

        for sort_type in ["hot", "top", "new"]:
            # Rate limit: 2 seconds between requests to stay safe
            time.sleep(2)

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

                if not title or (not body and not post.get("url", "")):
                    continue

                all_posts.append({
                    "id": post_id,
                    "platform": "reddit",
                    "title": title,
                    "body": body or f'[Link post: {post.get("url", "")}]',
                    "created_utc": created_utc,
                    "source": sub,
                    "url": f"{REDDIT_BASE}{permalink}",
                    "type": "post",
                })

            log.info(f"  r/{sub}/{sort_type}: {len(raw_posts)} posts fetched")

        if len(all_posts) >= max_items:
            break

    log.info(f"Reddit: Total {len(all_posts)} items scraped (via JSON, no API key)")
    return all_posts[:max_items]
