# scheduler/runner.py — Main pipeline orchestrator with deduplication

import json
import time
import hashlib
from datetime import datetime, timezone

from config.config_loader import get_config
from db.schema import create_tables
from db.writer import (
    insert_post, update_post_filter_scores, update_post_insight,
    update_post_app_idea, mark_posts_in_history, insert_run, update_run,
)
from db.reader import get_posts_by_ids, get_top_insights_from_today, get_post_parent_mapping
from scrapers.reddit_scraper import scrape_reddit
from scrapers.hackernews_scraper import scrape_hackernews
from scrapers.producthunt_scraper import scrape_producthunt
from analysis.gemini_client import analyze_with_gemini
from analysis.filters import build_filter_prompt, calculate_weighted_score
from analysis.insights import build_insight_prompt, build_app_idea_prompt
from utils.logger import setup_logger
from utils.helpers import sanitize_text, ensure_directory_exists

log = setup_logger()


def is_valid_post(post: dict) -> bool:
    """Ensure post has valid title and body."""
    title = sanitize_text(post.get("title", ""))
    body = sanitize_text(post.get("body", ""))
    return bool(title) and bool(body) and len(body) > 10


def content_hash(post: dict) -> str:
    """Create a content hash to detect duplicate/near-duplicate posts."""
    text = (post.get("title", "") + " " + post.get("body", "")).strip().lower()
    # Normalize whitespace
    text = " ".join(text.split())
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def deduplicate_posts(posts: list) -> list:
    """Remove duplicate posts based on content hash.
    Posts with identical or near-identical content are dropped regardless of source.
    """
    seen_hashes = set()
    seen_ids = set()
    unique = []

    for post in posts:
        pid = post.get("id", "")
        if pid in seen_ids:
            continue
        seen_ids.add(pid)

        h = content_hash(post)
        if h in seen_hashes:
            log.debug(f"  Duplicate skipped: {post.get('title', '')[:60]}")
            continue
        seen_hashes.add(h)

        unique.append(post)

    removed = len(posts) - len(unique)
    if removed > 0:
        log.info(f"Deduplication: removed {removed} duplicate posts")

    return unique


def run_pipeline(platforms: list[str] = None, limit: int = None,
                 skip_analysis: bool = False):
    """Run the full scraping and analysis pipeline.

    Args:
        platforms: List of platforms to scrape. None = all enabled.
        limit: Override max items per platform.
        skip_analysis: If True, only scrape without AI analysis.
    """
    config = get_config()
    start_time = time.time()

    ensure_directory_exists("data")
    ensure_directory_exists("logs")
    create_tables()

    log.info("🚀 Starting Pain Miner pipeline...")

    # Determine which platforms to scrape
    if platforms is None:
        platforms = []
        for pname in ["reddit", "hackernews", "producthunt"]:
            if config["platforms"].get(pname, {}).get("enabled", False):
                platforms.append(pname)

    if limit:
        config["scraper"]["max_items_per_platform"] = limit

    # ── Step 1: Scrape ──────────────────────────────────────────────
    all_scraped = []
    platform_str = ", ".join(platforms)
    run_id = insert_run(platform_str)

    for platform in platforms:
        log.info(f"Step 1: Scraping {platform}...")

        try:
            if platform == "reddit":
                posts = scrape_reddit()
            elif platform == "hackernews":
                posts = scrape_hackernews()
            elif platform == "producthunt":
                posts = scrape_producthunt()
            else:
                log.warning(f"Unknown platform: {platform}")
                continue

            for post in posts:
                insert_post(post)
            all_scraped.extend(posts)
            log.info(f"  → {platform}: {len(posts)} items")

        except Exception as e:
            log.error(f"Error scraping {platform}: {e}")

    if not all_scraped:
        log.warning("No posts found. Exiting pipeline.")
        update_run(run_id, 0, 0, time.time() - start_time, "no_data")
        return

    # ── Deduplication ───────────────────────────────────────────────
    all_scraped = deduplicate_posts(all_scraped)

    # Filter valid posts
    valid_posts = [p for p in all_scraped if is_valid_post(p)]
    log.info(f"Total scraped: {len(all_scraped)}, valid: {len(valid_posts)}")

    if skip_analysis:
        duration = time.time() - start_time
        update_run(run_id, len(valid_posts), 0, duration, "scrape_only")
        log.info(f"✅ Scraping complete. {len(valid_posts)} posts saved. ({duration:.1f}s)")
        return

    if not valid_posts:
        update_run(run_id, 0, 0, time.time() - start_time, "no_valid_posts")
        return

    # ── Step 2: Filter with AI ──────────────────────────────────────
    log.info(f"Step 2: Filtering {len(valid_posts)} posts with Gemini...")

    system_prompt = "You are a market research analyst. Respond with valid JSON only."
    high_potential = []
    filtered_ids = set()

    for i, post in enumerate(valid_posts, 1):
        log.info(f"  Filtering {i}/{len(valid_posts)}: {post['title'][:60]}")

        prompt = build_filter_prompt(post)
        scores = analyze_with_gemini(prompt, system_prompt)

        if scores:
            update_post_filter_scores(post["id"], scores)
            filtered_ids.add(post["id"])

            weighted = calculate_weighted_score(scores)
            threshold = config["scoring"]["min_score_threshold"]

            if weighted >= threshold:
                post["_scores"] = scores
                post["_weighted"] = weighted
                high_potential.append(post)
                log.info(f"    ✓ High potential (score: {weighted:.2f})")
            else:
                log.info(f"    ✗ Below threshold ({weighted:.2f} < {threshold})")
        else:
            log.warning(f"    ⚠ No response for {post['id']}")

        time.sleep(0.3)  # Rate limit

    # Mark below-threshold posts in history
    below_threshold = filtered_ids - {p["id"] for p in high_potential}
    if below_threshold:
        mark_posts_in_history(list(below_threshold))

    log.info(f"Step 2 complete: {len(high_potential)} high-potential posts")

    if not high_potential:
        duration = time.time() - start_time
        update_run(run_id, len(valid_posts), 0, duration, "no_high_potential")
        log.info("No high-potential posts found.")
        return

    # ── Step 3: Deep Insight ────────────────────────────────────────
    log.info(f"Step 3: Deep analysis of {len(high_potential)} posts...")

    system_prompt = "You are a product strategist. Respond with valid JSON only."
    insight_count = 0

    for i, post in enumerate(high_potential, 1):
        log.info(f"  Analyzing {i}/{len(high_potential)}: {post['title'][:60]}")

        prompt = build_insight_prompt(post)
        insight = analyze_with_gemini(prompt, system_prompt)

        if insight:
            update_post_insight(post["id"], insight)
            post["_insight"] = insight
            insight_count += 1
            log.info(f"    ✓ Insight: {insight.get('pain_point', '')[:80]}")
        else:
            log.warning(f"    ⚠ No insight for {post['id']}")

        time.sleep(0.3)

    # ── Step 4: Generate App Ideas ──────────────────────────────────
    log.info(f"Step 4: Generating app ideas for {insight_count} problems...")

    system_prompt = "You are an app development strategist. Respond with valid JSON only."
    idea_count = 0

    for post in high_potential:
        insight = post.get("_insight")
        if not insight:
            continue

        log.info(f"  Generating idea for: {post['title'][:60]}")

        prompt = build_app_idea_prompt(post, insight)
        app_idea = analyze_with_gemini(prompt, system_prompt)

        if app_idea:
            update_post_app_idea(post["id"], app_idea)
            idea_count += 1
            log.info(f"    💡 {app_idea.get('app_name', 'N/A')} ({app_idea.get('strategy', '')})")
        else:
            log.warning(f"    ⚠ No app idea for {post['id']}")

        time.sleep(0.3)

    # Mark insight-completed posts in history
    completed_ids = [p["id"] for p in high_potential if p.get("_insight")]
    if completed_ids:
        mark_posts_in_history(completed_ids)

    # ── Summary ─────────────────────────────────────────────────────
    duration = time.time() - start_time
    update_run(run_id, len(valid_posts), insight_count, duration, "completed")

    output_limit = config["scoring"]["output_top_n"]
    top_posts = get_top_insights_from_today(limit=output_limit)

    log.info(f"\n{'='*60}")
    log.info(f"✅ Pipeline complete in {duration:.1f}s")
    log.info(f"   Scraped: {len(valid_posts)} posts")
    log.info(f"   High potential: {len(high_potential)}")
    log.info(f"   Insights: {insight_count}")
    log.info(f"   App ideas: {idea_count}")
    log.info(f"{'='*60}")

    for i, post in enumerate(top_posts[:10], 1):
        log.info(
            f"  {i}. [{post.get('platform', '?')}] {post.get('title', '')[:60]} "
            f"— ROI: {post.get('roi_weight', 0)} | Tags: {post.get('tags', '')}"
        )

    return {
        "scraped": len(valid_posts),
        "high_potential": len(high_potential),
        "insights": insight_count,
        "app_ideas": idea_count,
        "duration": duration,
    }
