# scrapers/twitter_scraper.py — Twitter/X scraper using Twikit (no API key needed)

import os
import time
import json
import asyncio
from datetime import datetime, timezone, timedelta

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# Cookie file stores session so we don't re-login every time
COOKIE_FILE = "data/twitter_cookies.json"


def _get_twikit_client():
    """Create and authenticate a Twikit client."""
    try:
        from twikit import Client
    except ImportError:
        log.warning("Twikit not installed. Install with: pip install twikit")
        return None

    username = os.getenv("TWITTER_USERNAME", "")
    password = os.getenv("TWITTER_PASSWORD", "")

    if not username or not password:
        log.warning("Twitter credentials not set (TWITTER_USERNAME, TWITTER_PASSWORD). Skipping Twitter.")
        return None

    client = Client(language="en-US")

    # Try loading saved cookies first
    try:
        if os.path.exists(COOKIE_FILE):
            client.load_cookies(COOKIE_FILE)
            log.info("Twitter: Loaded saved session cookies")
            return client
    except Exception:
        log.info("Twitter: Saved cookies invalid, re-logging in...")

    # Login with credentials
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_login():
            await client.login(
                auth_info_1=username,
                auth_info_2=os.getenv("TWITTER_EMAIL", username),
                password=password,
            )

        loop.run_until_complete(do_login())
        loop.close()

        # Save cookies for next time
        client.save_cookies(COOKIE_FILE)
        log.info("Twitter: Login successful, cookies saved")
        return client
    except Exception as e:
        log.error(f"Twitter login failed: {e}")
        return None


def scrape_twitter() -> list:
    """Scrape Twitter/X for problem-related tweets using Twikit."""
    config = get_config()
    platform_config = config["platforms"].get("twitter", {})

    if not platform_config.get("enabled", False):
        log.info("Twitter scraping disabled")
        return []

    client = _get_twikit_client()
    if client is None:
        return []

    search_queries = platform_config.get("search_queries", [
        '"I wish there was" app OR tool',
        '"frustrated with" software OR app',
        '"looking for a tool" OR "need a better"',
        '"is there an app" OR "why is there no"',
        '"pain point" startup OR saas',
        '"hate using" OR "waste of time" tool OR app',
    ])

    max_items = config["scraper"]["max_items_per_platform"]
    all_posts = []
    seen_ids = set()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def search_tweets():
            nonlocal all_posts, seen_ids

            for query in search_queries:
                if len(all_posts) >= max_items:
                    break

                try:
                    log.info(f"Twitter: Searching '{query[:50]}...'")
                    tweets = await client.search_tweet(query, product="Latest", count=20)

                    for tweet in tweets:
                        tweet_id = f"twitter_{tweet.id}"

                        if tweet.id in seen_ids:
                            continue
                        seen_ids.add(tweet.id)

                        if is_already_processed(tweet_id):
                            continue

                        text = tweet.text or ""
                        if len(text) < 20:
                            continue

                        created_at = tweet.created_at_datetime if hasattr(tweet, 'created_at_datetime') else datetime.now(timezone.utc)

                        all_posts.append({
                            "id": tweet_id,
                            "platform": "twitter",
                            "title": text[:120],
                            "body": text,
                            "created_utc": created_at.timestamp() if hasattr(created_at, 'timestamp') else time.time(),
                            "source": "twitter_search",
                            "url": f"https://x.com/i/status/{tweet.id}",
                            "type": "post",
                        })

                    log.info(f"  Found {len(tweets)} tweets")

                except Exception as e:
                    log.warning(f"Twitter search error for '{query[:30]}': {e}")

                # Rate limit: 5 seconds between searches
                time.sleep(5)

        loop.run_until_complete(search_tweets())
        loop.close()

    except Exception as e:
        log.error(f"Twitter scraping error: {e}")

    log.info(f"Twitter: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
