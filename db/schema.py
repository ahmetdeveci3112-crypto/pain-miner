# db/schema.py — SQLite schema for local development

import sqlite3
import os
from config.config_loader import get_config
from utils.logger import setup_logger
from utils.helpers import ensure_directory_exists

log = setup_logger()


def get_db_path():
    config = get_config()
    return config["database"]["path"]


def create_tables():
    """Create all SQLite tables if they don't exist."""
    db_path = get_db_path()
    ensure_directory_exists(os.path.dirname(db_path))
    log.info(f"Initializing database at {db_path}")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        url TEXT,
        title TEXT,
        body TEXT,
        source TEXT,
        created_utc REAL,
        processed_at TEXT,
        relevance_score REAL,
        emotion_score REAL,
        pain_score REAL,
        implementability_score REAL,
        technical_depth_score REAL,
        tags TEXT,
        roi_weight INTEGER,
        community_type TEXT,
        type TEXT,
        parent_body TEXT,
        parent_post_id TEXT,
        insight_processed INTEGER DEFAULT 0,
        insight_processed_at TEXT,
        insight_data TEXT,
        app_idea TEXT,
        app_idea_processed INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id TEXT PRIMARY KEY,
        processed_at TEXT DEFAULT (datetime('now'))
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT DEFAULT (datetime('now')),
        finished_at TEXT,
        platform TEXT,
        posts_scraped INTEGER DEFAULT 0,
        problems_found INTEGER DEFAULT 0,
        duration_seconds REAL,
        status TEXT DEFAULT 'running'
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS app_ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id TEXT,
        app_name TEXT,
        app_type TEXT,
        description TEXT,
        target_audience TEXT,
        monetization TEXT,
        complexity TEXT,
        tech_stack TEXT,
        traffic_potential TEXT,
        revenue_potential TEXT,
        mvp_features TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (post_id) REFERENCES posts(id)
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT NOT NULL,
        item_type TEXT NOT NULL,
        action TEXT NOT NULL,
        note TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(item_id, item_type, action)
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        tags TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    """)

    # Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_processed_at ON posts(processed_at);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_relevance ON posts(relevance_score);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_roi ON posts(roi_weight);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_app_ideas_post ON app_ideas(post_id);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_item ON user_actions(item_id, item_type);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_action ON user_actions(action);")

    conn.commit()
    conn.close()
    log.info("Database tables created successfully")


if __name__ == "__main__":
    create_tables()
    print(f"Database initialized at {get_db_path()}")
