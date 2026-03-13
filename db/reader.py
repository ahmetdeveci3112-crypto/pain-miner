# db/reader.py — Database read operations

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


def is_already_processed(post_id: str) -> bool:
    """Check if a post has already been processed."""
    conn = _get_connection()
    try:
        result = conn.execute(
            "SELECT 1 FROM history WHERE id = ?", (post_id,)
        ).fetchone()
        return result is not None
    except sqlite3.Error as e:
        print(f"[SQLite is_already_processed Error] {e}")
        return False


def get_posts_by_ids(post_ids: set, require_unprocessed: bool = False) -> list:
    """Retrieve post records for a set of IDs."""
    if not post_ids:
        return []

    conn = _get_connection()
    placeholders = ",".join("?" for _ in post_ids)
    query = f"SELECT * FROM posts WHERE id IN ({placeholders})"
    if require_unprocessed:
        query += " AND (insight_processed IS NULL OR insight_processed = 0)"

    try:
        rows = conn.execute(query, tuple(post_ids)).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[SQLite get_posts_by_ids Error] {e}")
        return []


def get_unprocessed_posts(limit: int = 100) -> list:
    """Get posts that haven't been analyzed yet."""
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM posts
            WHERE insight_processed = 0 OR insight_processed IS NULL
            ORDER BY created_utc DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[SQLite get_unprocessed_posts Error] {e}")
        return []


def get_top_insights(limit: int = 20, platform: str = None) -> list:
    """Get top-scoring insights."""
    conn = _get_connection()
    try:
        query = """
            SELECT * FROM posts
            WHERE insight_processed = 1
        """
        params = []
        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY roi_weight DESC, relevance_score DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[SQLite get_top_insights Error] {e}")
        return []


def get_top_insights_from_today(limit: int = 20) -> list:
    """Get today's top insights."""
    today = datetime.now(timezone.utc).date().isoformat()
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM posts
            WHERE date(processed_at) = ? AND insight_processed = 1
            ORDER BY roi_weight DESC, relevance_score DESC
            LIMIT ?
        """, (today, limit)).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[SQLite get_top_insights_from_today Error] {e}")
        return []


def get_app_ideas(limit: int = 50) -> list:
    """Get all generated app ideas with their parent post info."""
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT a.*, p.title as post_title, p.url as post_url,
                   p.platform, p.source, p.roi_weight as post_roi
            FROM app_ideas a
            JOIN posts p ON a.post_id = p.id
            ORDER BY a.created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[SQLite get_app_ideas Error] {e}")
        return []


def get_stats() -> dict:
    """Get database statistics."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        analyzed = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE insight_processed = 1"
        ).fetchone()[0]
        ideas = conn.execute("SELECT COUNT(*) FROM app_ideas").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

        platform_counts = {}
        rows = conn.execute(
            "SELECT platform, COUNT(*) as cnt FROM posts GROUP BY platform"
        ).fetchall()
        for row in rows:
            platform_counts[row[0]] = row[1]

        return {
            "total_posts": total,
            "analyzed_posts": analyzed,
            "app_ideas": ideas,
            "total_runs": runs,
            "by_platform": platform_counts,
        }
    except sqlite3.Error as e:
        print(f"[SQLite get_stats Error] {e}")
        return {}


def get_post_parent_mapping(post_ids: set) -> dict:
    """Return {id: parent_post_id} for dedup."""
    if not post_ids:
        return {}
    conn = _get_connection()
    placeholders = ",".join("?" for _ in post_ids)
    try:
        rows = conn.execute(
            f"SELECT id, parent_post_id FROM posts WHERE id IN ({placeholders})",
            tuple(post_ids),
        ).fetchall()
        return {row["id"]: row["parent_post_id"] for row in rows}
    except sqlite3.Error as e:
        print(f"[SQLite get_post_parent_mapping Error] {e}")
        return {}
