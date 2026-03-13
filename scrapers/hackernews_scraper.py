# scrapers/hackernews_scraper.py — Hacker News scraper using Firebase API

from typing import Optional, List
import requests
import time
from datetime import datetime, timezone

from utils.logger import setup_logger
from utils.helpers import sanitize_text
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
HN_WEB_BASE = "https://news.ycombinator.com"


def fetch_item(item_id: int) -> Optional[dict]:
    """Fetch a single HN item by ID."""
    try:
        resp = requests.get(f"{HN_API_BASE}/item/{item_id}.json", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        log.debug(f"Failed to fetch HN item {item_id}: {e}")
    return None


def fetch_story_ids(category: str, limit: int = 100) -> List[int]:
    """Fetch story IDs for a given category."""
    endpoint_map = {
        "top": "topstories",
        "new": "newstories",
        "best": "beststories",
        "ask": "askstories",
        "show": "showstories",
    }

    endpoint = endpoint_map.get(category, "topstories")
    try:
        resp = requests.get(f"{HN_API_BASE}/{endpoint}.json", timeout=10)
        if resp.status_code == 200:
            ids = resp.json()
            return ids[:limit] if ids else []
    except Exception as e:
        log.error(f"Failed to fetch HN {category} stories: {e}")
    return []


def fetch_comments(story: dict, max_comments: int = 10) -> List[dict]:
    """Fetch top-level comments for a story."""
    comments = []
    kids = story.get("kids", [])

    for kid_id in kids[:max_comments]:
        item = fetch_item(kid_id)
        if item and item.get("type") == "comment" and item.get("text"):
            comments.append(item)
        time.sleep(0.05)  # Be nice to the API

    return comments


def scrape_hackernews() -> list:
    """Scrape Hacker News posts and comments."""
    config = get_config()
    platform_config = config["platforms"]["hackernews"]

    if not platform_config.get("enabled", True):
        log.info("Hacker News scraping disabled")
        return []

    categories = platform_config.get("categories", ["ask", "show", "top"])
    max_items = config["scraper"]["max_items_per_platform"]
    include_comments = config["scraper"].get("include_comments", True)
    min_days = config["scraper"]["min_post_age_days"]
    max_days = config["scraper"]["max_post_age_days"]

    all_posts = []
    per_category = max(10, max_items // len(categories))

    for category in categories:
        log.info(f"Fetching HN {category} stories...")
        story_ids = fetch_story_ids(category, limit=per_category * 3)

        for story_id in story_ids:
            if len(all_posts) >= max_items:
                break

            story = fetch_item(story_id)
            if not story:
                continue

            # Check if it's a story/ask with text
            story_type = story.get("type", "")
            if story_type not in ("story", "poll"):
                continue

            # Check age
            created_utc = story.get("time", 0)
            now = datetime.now(timezone.utc).timestamp()
            age_days = (now - created_utc) / 86400

            if age_days < min_days or age_days > max_days:
                continue

            hn_id = f"hn_{story['id']}"
            if is_already_processed(hn_id):
                continue

            title = story.get("title", "")
            text = story.get("text", "")
            url = story.get("url", f"{HN_WEB_BASE}/item?id={story['id']}")
            hn_url = f"{HN_WEB_BASE}/item?id={story['id']}"

            # For stories with external URLs, use the HN discussion page
            post_data = {
                "id": hn_id,
                "platform": "hackernews",
                "title": title,
                "body": text or f"[External link: {url}]",
                "created_utc": created_utc,
                "source": category,
                "url": hn_url,
                "type": "post",
            }
            all_posts.append(post_data)

            # Fetch comments
            if include_comments and story.get("descendants", 0) > 0:
                comments = fetch_comments(story, max_comments=5)
                for comment in comments:
                    c_id = f"hn_{comment['id']}"
                    if is_already_processed(c_id):
                        continue

                    all_posts.append({
                        "id": c_id,
                        "platform": "hackernews",
                        "title": title,
                        "body": comment.get("text", ""),
                        "parent_body": text,
                        "created_utc": comment.get("time", 0),
                        "source": category,
                        "url": f"{HN_WEB_BASE}/item?id={comment['id']}",
                        "type": "comment",
                        "parent_post_id": hn_id,
                    })

            time.sleep(0.1)  # Rate limiting

    log.info(f"Hacker News: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
