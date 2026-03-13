# db/writer.py — Database write operations

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from config.config_loader import get_config

config = get_config()
DB_PATH = config["database"]["path"]

_conn = None


def _get_connection():
    global _conn
    if _conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL;")
    return _conn


def insert_post(post: dict, community_type: str = "primary"):
    """Insert a scraped post into the database."""
    conn = _get_connection()
    try:
        conn.execute("""
        INSERT OR IGNORE INTO posts (
            id, platform, url, title, body, source, created_utc,
            processed_at, community_type, type, parent_body, parent_post_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post["id"],
            post.get("platform", "unknown"),
            post.get("url", ""),
            post.get("title", ""),
            post.get("body", ""),
            post.get("source", ""),
            post.get("created_utc", 0),
            datetime.now(timezone.utc).date().isoformat(),
            community_type,
            post.get("type", "post"),
            post.get("parent_body", ""),
            post.get("parent_post_id"),
        ))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[SQLite Insert Error] {e}")


def update_post_filter_scores(post_id: str, scores: dict):
    """Update filtering phase scores."""
    conn = _get_connection()
    try:
        conn.execute("""
        UPDATE posts SET
            relevance_score = ?,
            emotion_score = ?,
            pain_score = ?,
            implementability_score = ?,
            technical_depth_score = ?,
            processed_at = ?
        WHERE id = ?
        """, (
            scores.get("relevance_score"),
            scores.get("emotional_intensity"),
            scores.get("pain_point_clarity"),
            scores.get("implementability_score"),
            scores.get("technical_depth_score"),
            datetime.now(timezone.utc).date().isoformat(),
            post_id,
        ))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[SQLite update_post_filter_scores Error] {e}")


def update_post_insight(post_id: str, insight: dict):
    """Update deeper insights (tags, roi_weight, full insight data)."""
    conn = _get_connection()
    try:
        tags = ", ".join(insight.get("tags", []))
        roi = insight.get("roi_weight", 0)
        insight_json = json.dumps(insight, ensure_ascii=False)

        conn.execute("""
        UPDATE posts SET
            tags = ?,
            roi_weight = ?,
            insight_processed = 1,
            insight_processed_at = ?,
            insight_data = ?
        WHERE id = ?
        """, (
            tags, roi,
            datetime.now(timezone.utc).isoformat(),
            insight_json,
            post_id,
        ))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[SQLite update_post_insight Error] {e}")


def update_post_app_idea(post_id: str, app_idea: dict):
    """Insert an app idea generated from a problem."""
    conn = _get_connection()
    try:
        conn.execute("""
        INSERT INTO app_ideas (
            post_id, app_name, app_type, description, target_audience,
            monetization, complexity, tech_stack, traffic_potential,
            revenue_potential, mvp_features
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post_id,
            app_idea.get("app_name", ""),
            app_idea.get("app_type", ""),
            app_idea.get("description", ""),
            app_idea.get("target_audience", ""),
            app_idea.get("monetization", ""),
            app_idea.get("complexity", ""),
            app_idea.get("tech_stack", ""),
            app_idea.get("traffic_potential", ""),
            app_idea.get("revenue_potential", ""),
            json.dumps(app_idea.get("mvp_features", []), ensure_ascii=False),
        ))

        conn.execute("""
        UPDATE posts SET app_idea = ?, app_idea_processed = 1 WHERE id = ?
        """, (json.dumps(app_idea, ensure_ascii=False), post_id))

        conn.commit()
    except sqlite3.Error as e:
        print(f"[SQLite update_post_app_idea Error] {e}")


def mark_posts_in_history(post_ids: list[str]):
    """Bulk-insert post IDs into the history table."""
    conn = _get_connection()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO history (id, processed_at) VALUES (?, ?)",
            [(pid, datetime.now(timezone.utc).isoformat()) for pid in post_ids],
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"[SQLite mark_posts_in_history Error] {e}")


def insert_run(platform: str) -> int:
    """Record a new pipeline run and return its ID."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO runs (platform) VALUES (?)", (platform,)
    )
    conn.commit()
    return cursor.lastrowid


def update_run(run_id: int, posts_scraped: int, problems_found: int,
               duration: float, status: str = "completed"):
    """Update a pipeline run record."""
    conn = _get_connection()
    conn.execute("""
    UPDATE runs SET
        finished_at = datetime('now'),
        posts_scraped = ?,
        problems_found = ?,
        duration_seconds = ?,
        status = ?
    WHERE id = ?
    """, (posts_scraped, problems_found, duration, status, run_id))
    conn.commit()
