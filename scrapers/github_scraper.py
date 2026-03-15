# scrapers/github_scraper.py — GitHub scraper using public REST Search API

import requests
import time
import random
import hashlib
from datetime import datetime, timezone, timedelta

from utils.logger import setup_logger
from config.config_loader import get_config
from db.reader import is_already_processed

log = setup_logger()

# GitHub Search API — no auth needed, 10 requests/minute limit
GITHUB_SEARCH_URL = "https://api.github.com/search/issues"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
]

# Pain-point search queries for GitHub Issues/Discussions
SEARCH_QUERIES = [
    "looking for tool",
    "wish there was",
    "frustrated with",
    "pain point",
    "is there a tool",
    "need a better way",
    "alternative to",
    "hate using",
    "any good tool for",
    "manually doing",
]


def _search_github(query, per_page=15):
    """Search GitHub issues/discussions for pain points."""
    # Only search issues/discussions from the last 30 days
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    params = {
        "q": f'"{query}" created:>{since} is:issue',
        "sort": "created",
        "order": "desc",
        "per_page": per_page,
    }

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        resp = requests.get(GITHUB_SEARCH_URL, params=params, headers=headers, timeout=15)

        if resp.status_code == 200:
            return resp.json().get("items", [])
        elif resp.status_code == 403:
            log.warning("GitHub API rate limited. Waiting 60s...")
            time.sleep(60)
            return []
        elif resp.status_code == 422:
            log.warning(f"GitHub search validation error for query: {query}")
            return []
        else:
            log.warning(f"GitHub search returned {resp.status_code}")
            return []
    except Exception as e:
        log.warning(f"GitHub search error: {e}")
        return []


def scrape_github() -> list:
    """Scrape GitHub issues/discussions for pain points."""
    config = get_config()
    platform_config = config["platforms"].get("github", {})

    if not platform_config.get("enabled", False):
        log.info("GitHub scraping disabled")
        return []

    max_items = config["scraper"]["max_items_per_platform"]
    search_terms = platform_config.get("search_queries", SEARCH_QUERIES)

    all_posts = []
    seen_ids = set()

    log.info(f"GitHub: Searching issues with {len(search_terms)} queries...")

    for i, query in enumerate(search_terms):
        if len(all_posts) >= max_items:
            break

        log.info(f"  GitHub search ({i+1}/{len(search_terms)}): \"{query}\"")

        # Rate limit: 6s between requests (10 req/min limit)
        if i > 0:
            time.sleep(6 + random.uniform(0.5, 2.0))

        items = _search_github(query, per_page=10)

        for item in items:
            if len(all_posts) >= max_items:
                break

            gh_id = str(item.get("id", ""))
            if not gh_id or gh_id in seen_ids:
                continue
            seen_ids.add(gh_id)

            post_id = f"github_{gh_id}"
            if is_already_processed(post_id):
                continue

            title = item.get("title", "").strip()
            body = item.get("body", "") or ""
            body = body[:2000]  # Truncate very long issues
            url = item.get("html_url", "")

            if not title or len(title) < 5:
                continue

            # Extract repo name as source
            repo_url = item.get("repository_url", "")
            source = repo_url.split("/repos/")[-1] if "/repos/" in repo_url else "github"

            # Parse created date
            created_at = item.get("created_at", "")
            try:
                created_utc = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                ).timestamp()
            except Exception:
                created_utc = datetime.now(timezone.utc).timestamp()

            all_posts.append({
                "id": post_id,
                "platform": "github",
                "title": title,
                "body": body if body and len(body) > 10 else title,
                "created_utc": created_utc,
                "source": source,
                "url": url,
                "type": "issue",
            })

        log.info(f"    Found {len(items)} items")

    log.info(f"GitHub: Total {len(all_posts)} items scraped")
    return all_posts[:max_items]
