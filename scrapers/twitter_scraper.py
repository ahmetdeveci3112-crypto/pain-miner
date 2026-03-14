# scrapers/twitter_scraper.py — Twitter/X scraper via internal API + cookie auth
# No API key, no Twikit dependency — uses browser cookies directly.

import os
import requests
import time
import random
import json
from datetime import datetime, timezone

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# Twitter's public bearer token (same for all clients — extracted from the web app)
BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

SEARCH_URL = "https://x.com/i/api/2/search/adaptive.json"

# Guest token URL
GUEST_TOKEN_URL = "https://api.x.com/1.1/guest/activate.json"


def _build_headers(auth_token, ct0):
    """Build headers for Twitter's internal API using cookie auth."""
    return {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "x-csrf-token": ct0,
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://x.com/search",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
    }


def _search_tweets(query, auth_token, ct0, count=20):
    """Search for tweets using Twitter's internal search API."""
    params = {
        "q": query,
        "tweet_search_mode": "live",
        "query_source": "typed_query",
        "count": count,
        "result_filter": "tweet",
        "pc": "1",
        "spelling_corrections": "1",
        "include_ext_edit_control": "true",
        "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,birdwatchPivot,superFollowMetadata,unmentionInfo,editControl",
    }

    headers = _build_headers(auth_token, ct0)

    try:
        resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=15)

        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            log.warning("Twitter rate limited (429). Waiting 30s...")
            time.sleep(30)
            return None
        elif resp.status_code == 401:
            log.warning("Twitter auth failed (401) — cookies may be expired")
            return None
        else:
            log.warning(f"Twitter search returned {resp.status_code}")
            return None
    except Exception as e:
        log.warning(f"Twitter search error: {e}")
        return None


def _extract_tweets_from_response(data):
    """Extract tweet objects from Twitter's adaptive search response."""
    tweets = []
    if not data:
        return tweets

    # Twitter's adaptive search response has tweets in globalObjects.tweets
    global_tweets = data.get("globalObjects", {}).get("tweets", {})
    global_users = data.get("globalObjects", {}).get("users", {})

    for tweet_id, tweet_data in global_tweets.items():
        user_id = tweet_data.get("user_id_str", "")
        user_data = global_users.get(user_id, {})

        text = tweet_data.get("full_text", "") or tweet_data.get("text", "")
        if not text or len(text) < 20:
            continue

        # Skip retweets
        if text.startswith("RT @"):
            continue

        created_at = tweet_data.get("created_at", "")
        try:
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            created_utc = dt.timestamp()
        except Exception:
            created_utc = datetime.now(timezone.utc).timestamp()

        screen_name = user_data.get("screen_name", "unknown")

        tweets.append({
            "tweet_id": tweet_id,
            "text": text,
            "user": screen_name,
            "created_utc": created_utc,
            "retweet_count": tweet_data.get("retweet_count", 0),
            "favorite_count": tweet_data.get("favorite_count", 0),
        })

    return tweets


def scrape_twitter() -> list:
    """Scrape Twitter/X for problem-related tweets using cookie auth."""
    config = get_config()
    platform_config = config["platforms"]["twitter"]

    if not platform_config.get("enabled", True):
        log.info("Twitter/X scraping disabled")
        return []

    # Get cookies from env vars
    auth_token = os.getenv("TWITTER_AUTH_TOKEN", "")
    ct0 = os.getenv("TWITTER_CT0", "")

    if not auth_token or not ct0:
        log.warning("Twitter: TWITTER_AUTH_TOKEN and TWITTER_CT0 env vars required")
        return []

    log.info("Twitter/X: Using cookie auth (no API key needed)")

    search_queries = platform_config.get("search_queries", [
        '"I wish there was" app OR tool',
        '"frustrated with" software OR app',
        '"why is there no" app OR service',
        '"someone should build" app OR tool',
        '"need a better" app OR tool OR software',
        '"pain point" startup OR product',
    ])

    max_items = config["scraper"]["max_items_per_platform"]
    all_posts = []
    seen_ids = set()

    for query in search_queries:
        if len(all_posts) >= max_items:
            break

        log.info(f"Twitter search: {query[:50]}...")

        # Rate limit: 5-8 seconds between searches
        time.sleep(5 + random.uniform(1, 3))

        data = _search_tweets(query, auth_token, ct0, count=20)
        tweets = _extract_tweets_from_response(data)

        for tweet in tweets:
            tweet_id = tweet["tweet_id"]
            post_id = f"twitter_{tweet_id}"

            if tweet_id in seen_ids:
                continue
            seen_ids.add(tweet_id)

            if is_already_processed(post_id):
                continue

            text = tweet["text"]
            user = tweet["user"]

            all_posts.append({
                "id": post_id,
                "platform": "twitter",
                "title": f"@{user}: {text[:100]}",
                "body": text,
                "created_utc": tweet["created_utc"],
                "source": "twitter",
                "url": f"https://x.com/{user}/status/{tweet_id}",
                "type": "post",
            })

        log.info(f"  → {len(tweets)} tweets found for query")

    log.info(f"Twitter/X: Total {len(all_posts)} items scraped (via cookie auth)")
    return all_posts[:max_items]
