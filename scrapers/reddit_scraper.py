# scrapers/reddit_scraper.py — Reddit scraper adapted from Reddit_Scrapper

import datetime
import socket
import time

from utils.logger import setup_logger
from utils.helpers import sanitize_text
from config.config_loader import get_config
from db.reader import is_already_processed
from scrapers.rate_limiter import RateLimiter

socket.setdefaulttimeout(15)

log = setup_logger()


def _get_reddit_client():
    """Create and return a PRAW Reddit client."""
    import praw
    config = get_config()
    reddit_config = config.get("reddit", {})

    if not reddit_config.get("client_id"):
        log.warning("Reddit API credentials not configured. Skipping Reddit.")
        return None

    return praw.Reddit(
        client_id=reddit_config["client_id"],
        client_secret=reddit_config["client_secret"],
        user_agent=reddit_config.get("user_agent", "pain-miner:v1.0"),
        username=reddit_config.get("username"),
        password=reddit_config.get("password"),
    )


def is_post_in_age_range(post_timestamp, min_days, max_days) -> bool:
    post_date = datetime.datetime.fromtimestamp(post_timestamp, tz=datetime.timezone.utc)
    age_days = (datetime.datetime.now(datetime.timezone.utc) - post_date).days
    return min_days <= age_days <= max_days


def safe_fetch(generator, name):
    """Safely fetch from a Reddit listing generator."""
    try:
        log.info(f"→ Fetching {name}...")
        return list(generator)
    except Exception as e:
        log.error(f"Error while fetching {name}: {e}")
        return []


def fetch_posts_from_subreddit(reddit, subreddit_name, limiter, limit=200) -> list:
    """Fetch posts (and optionally comments) from a subreddit."""
    config = get_config()
    min_days = config["scraper"]["min_post_age_days"]
    max_days = config["scraper"]["max_post_age_days"]
    include_comments = config["scraper"].get("include_comments", False)

    results = []
    seen_ids = set()

    try:
        log.info(f"Fetching posts from r/{subreddit_name}...")
        subreddit = reddit.subreddit(subreddit_name)
        combined = []

        for fetch_name, fetch_method in [
            ("top", subreddit.top(time_filter="month", limit=limit)),
            ("hot", subreddit.hot(limit=limit)),
            ("new", subreddit.new(limit=limit)),
        ]:
            limiter.wait()
            posts = safe_fetch(fetch_method, f"r/{subreddit_name}/{fetch_name}")
            combined.extend(posts)

        log.info(f"Total fetched from r/{subreddit_name}: {len(combined)}")

        for post in combined:
            if post.id in seen_ids:
                continue
            seen_ids.add(post.id)

            if not is_post_in_age_range(post.created_utc, min_days, max_days):
                continue
            if is_already_processed(f"reddit_{post.id}"):
                continue

            results.append({
                "id": f"reddit_{post.id}",
                "platform": "reddit",
                "title": post.title,
                "body": post.selftext or "",
                "created_utc": post.created_utc,
                "source": subreddit_name,
                "url": f"https://www.reddit.com{post.permalink}",
                "type": "post",
            })

            if include_comments:
                try:
                    limiter.wait()
                    post.comments.replace_more(limit=0)
                    for comment in post.comments.list()[:10]:  # Top 10 comments
                        if comment.id in seen_ids:
                            continue
                        seen_ids.add(comment.id)

                        if not is_post_in_age_range(comment.created_utc, min_days, max_days):
                            continue
                        if is_already_processed(f"reddit_{comment.id}"):
                            continue

                        results.append({
                            "id": f"reddit_{comment.id}",
                            "platform": "reddit",
                            "title": post.title,
                            "body": comment.body,
                            "parent_body": post.selftext,
                            "created_utc": comment.created_utc,
                            "source": subreddit_name,
                            "url": f"https://www.reddit.com{comment.permalink}",
                            "type": "comment",
                            "parent_post_id": f"reddit_{post.id}",
                        })
                except Exception as e:
                    log.warning(f"Failed to fetch comments for {post.id}: {e}")

    except Exception as e:
        log.error(f"Error fetching from r/{subreddit_name}: {e}")

    log.info(f"r/{subreddit_name}: {len(results)} items collected")
    return results


def scrape_reddit() -> list:
    """Scrape configured subreddits and return all collected posts."""
    config = get_config()
    reddit = _get_reddit_client()
    if reddit is None:
        return []

    platform_config = config["platforms"]["reddit"]
    subreddits = platform_config["subreddits"]["primary"]
    max_items = config["scraper"]["max_items_per_platform"]
    rate_limit = config["scraper"].get("rate_limit_per_minute", 60)
    limiter = RateLimiter(rate_limit)

    all_posts = []

    per_subreddit = max(5, max_items // len(subreddits))

    for sub in subreddits:
        posts = fetch_posts_from_subreddit(reddit, sub, limiter, limit=per_subreddit)
        all_posts.extend(posts)

        if len(all_posts) >= max_items:
            break

    log.info(f"Reddit: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
