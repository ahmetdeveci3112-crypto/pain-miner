# scrapers/reddit_scraper.py — Reddit scraper with OAuth2 app-only flow for datacenter access

import os
import requests
import time
import datetime
import random

from utils.logger import setup_logger
from utils.helpers import sanitize_text
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# Reddit blocks ALL non-API requests from datacenter IPs (Fly.io, AWS, etc).
# The ONLY way to scrape Reddit from a server is via the OAuth API.
# "Application Only" OAuth is FREE and requires no user interaction,
# just a client_id and client_secret from https://www.reddit.com/prefs/apps
OAUTH_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_API_BASE = "https://oauth.reddit.com"

# Fallback for local/residential IPs where JSON endpoints still work
PUBLIC_BASE = "https://old.reddit.com"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
]

# Cache the OAuth token
_oauth_token = None
_oauth_token_expiry = 0


def _get_oauth_token():
    """Get an OAuth2 application-only access token from Reddit."""
    global _oauth_token, _oauth_token_expiry

    # Return cached token if still valid
    if _oauth_token and time.time() < _oauth_token_expiry - 60:
        return _oauth_token

    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return None

    try:
        resp = requests.post(
            OAUTH_TOKEN_URL,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": "PainMiner/2.0 by pain-miner-bot"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            _oauth_token = data["access_token"]
            _oauth_token_expiry = time.time() + data.get("expires_in", 3600)
            log.info("Reddit OAuth token acquired successfully")
            return _oauth_token
        else:
            log.warning(f"Reddit OAuth failed: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        log.error(f"Reddit OAuth error: {e}")

    return None


def _fetch_oauth(url):
    """Fetch from Reddit OAuth API."""
    token = _get_oauth_token()
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "PainMiner/2.0 by pain-miner-bot",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            log.warning("Reddit OAuth rate limited, waiting 10s...")
            time.sleep(10)
        else:
            log.warning(f"Reddit OAuth returned {resp.status_code}")
    except Exception as e:
        log.warning(f"Reddit OAuth fetch error: {e}")

    return None


def _fetch_public_json(url):
    """Fetch from public JSON endpoint (works from residential IPs)."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 403:
            return None  # Datacenter IP blocked
    except Exception:
        pass
    return None


def is_post_in_age_range(post_timestamp, min_days, max_days) -> bool:
    post_date = datetime.datetime.fromtimestamp(post_timestamp, tz=datetime.timezone.utc)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - post_date).days
    return min_days <= age_days <= max_days


def fetch_subreddit_posts(subreddit_name, sort="hot", limit=25) -> list:
    """Fetch posts from a subreddit. Tries OAuth API first, falls back to public JSON."""
    # Try OAuth API first (works from datacenter IPs)
    oauth_url = f"{OAUTH_API_BASE}/r/{subreddit_name}/{sort}?limit={limit}&raw_json=1&t=month"
    data = _fetch_oauth(oauth_url)

    # Fallback to public JSON (works from residential IPs)
    if data is None:
        public_url = f"{PUBLIC_BASE}/r/{subreddit_name}/{sort}.json?limit={limit}&raw_json=1&t=month"
        data = _fetch_public_json(public_url)

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
    """Scrape subreddits. Uses OAuth API on servers, public JSON locally."""
    config = get_config()
    platform_config = config["platforms"]["reddit"]

    if not platform_config.get("enabled", True):
        log.info("Reddit scraping disabled")
        return []

    # Check if OAuth is available
    has_oauth = bool(os.getenv("REDDIT_CLIENT_ID")) and bool(os.getenv("REDDIT_CLIENT_SECRET"))
    if has_oauth:
        log.info("Reddit: Using OAuth API (server mode)")
    else:
        log.info("Reddit: Using public JSON endpoints (local mode)")

    subreddits = platform_config["subreddits"]["primary"]
    max_items = config["scraper"]["max_items_per_platform"]
    min_days = config["scraper"]["min_post_age_days"]
    max_days = config["scraper"]["max_post_age_days"]

    all_posts = []
    seen_ids = set()
    per_subreddit = max(10, max_items // len(subreddits))

    for sub in subreddits:
        log.info(f"Fetching r/{sub}...")

        for sort_type in ["hot", "new"]:
            # Rate limit: 2-3 seconds between requests
            time.sleep(2 + random.uniform(0.5, 1.5))

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

                post_body = body
                if not post_body:
                    ext_url = post.get("url", "")
                    if ext_url:
                        post_body = f"[Link post: {ext_url}]"
                    else:
                        post_body = title

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

            log.info(f"  r/{sub}/{sort_type}: {len(raw_posts)} posts")

        if len(all_posts) >= max_items:
            break

    log.info(f"Reddit: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
