# api.py — Pain Miner FastAPI Web Server

import asyncio
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.config_loader import get_config
from db.schema import create_tables
from db.reader import get_stats, get_top_insights, get_app_ideas
from utils.helpers import ensure_directory_exists
from utils.logger import setup_logger

log = setup_logger()
app = FastAPI(title="Pain Miner", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Scrape state ────────────────────────────────────────────────────
_scrape_lock = threading.Lock()
_scrape_status = {
    "running": False,
    "last_run": None,
    "result": None,
    "error": None,
}


# ── Auto Scheduler ─────────────────────────────────────────────────
_scheduler = None

def _auto_scrape_job():
    """Background job: run the full pipeline automatically."""
    global _scrape_status
    with _scrape_lock:
        if _scrape_status["running"]:
            log.info("⏭ Auto-scrape skipped — manual scrape already running")
            return
        _scrape_status["running"] = True
        _scrape_status["error"] = None
        _scrape_status["result"] = None

    try:
        from scheduler.runner import run_pipeline
        log.info("🕐 Auto-scheduler: starting pipeline...")
        result = run_pipeline()
        with _scrape_lock:
            _scrape_status["result"] = result
            _scrape_status["last_run"] = datetime.now(timezone.utc).isoformat()
        log.info(f"🕐 Auto-scheduler: pipeline complete — {result}")
    except Exception as e:
        log.error(f"🕐 Auto-scheduler error: {e}")
        with _scrape_lock:
            _scrape_status["error"] = str(e)
    finally:
        with _scrape_lock:
            _scrape_status["running"] = False


# ── Startup ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    ensure_directory_exists("data")
    ensure_directory_exists("logs")
    create_tables()

    # Start auto-scheduler
    global _scheduler
    config = get_config()
    sched_config = config.get("scheduler", {})
    if sched_config.get("enabled", False):
        interval = sched_config.get("interval_hours", 1)
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(
            _auto_scrape_job,
            IntervalTrigger(hours=interval),
            id="auto_scrape",
            name=f"Auto scrape every {interval}h",
            replace_existing=True,
        )
        _scheduler.start()
        log.info(f"🕐 Auto-scheduler started: every {interval} hour(s)")


# ── API Routes ──────────────────────────────────────────────────────
@app.get("/api/stats")
async def api_stats():
    """Dashboard statistics."""
    stats = get_stats()
    return stats


@app.get("/api/problems")
async def api_problems(
    limit: int = Query(20, ge=1, le=200),
    platform: str = Query(None),
):
    """Top problems/insights sorted by ROI weight."""
    posts = get_top_insights(limit=limit, platform=platform)

    results = []
    for post in posts:
        insight_data = {}
        if post.get("insight_data"):
            try:
                insight_data = json.loads(post["insight_data"])
            except (json.JSONDecodeError, TypeError):
                pass

        results.append({
            "id": post.get("id"),
            "platform": post.get("platform", "unknown"),
            "title": post.get("title", ""),
            "url": post.get("url", ""),
            "source": post.get("source", ""),
            "roi_weight": post.get("roi_weight", 0),
            "relevance_score": post.get("relevance_score"),
            "pain_score": post.get("pain_score"),
            "emotion_score": post.get("emotion_score"),
            "tags": post.get("tags", ""),
            "pain_point": insight_data.get("pain_point", ""),
            "product_opportunity": insight_data.get("product_opportunity", ""),
            "processed_at": post.get("processed_at", ""),
        })

    return results


@app.get("/api/ideas")
async def api_ideas(
    limit: int = Query(500, ge=1, le=1000),
):
    """Generated app ideas."""
    ideas = get_app_ideas(limit=limit)

    results = []
    for idea in ideas:
        mvp_features = []
        raw = idea.get("mvp_features", "")
        if raw:
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(parsed, list):
                    mvp_features = parsed
            except (json.JSONDecodeError, TypeError):
                pass

        results.append({
            "id": idea.get("id"),
            "app_name": idea.get("app_name", ""),
            "app_type": idea.get("app_type", ""),
            "description": idea.get("description", ""),
            "target_audience": idea.get("target_audience", ""),
            "monetization": idea.get("monetization", ""),
            "complexity": idea.get("complexity", ""),
            "tech_stack": idea.get("tech_stack", ""),
            "traffic_potential": idea.get("traffic_potential", ""),
            "revenue_potential": idea.get("revenue_potential", ""),
            "mvp_features": mvp_features,
            "post_title": idea.get("post_title", ""),
            "post_url": idea.get("post_url", ""),
            "platform": idea.get("platform", ""),
            "created_at": idea.get("created_at", ""),
        })

    return results


@app.get("/api/runs")
async def api_runs():
    """Pipeline run history."""
    from db.reader import _get_connection
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 50"
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/scrape")
async def api_scrape(
    platform: str = Query(None),
    limit: int = Query(None),
):
    """Start a scrape pipeline in the background."""
    global _scrape_status

    with _scrape_lock:
        if _scrape_status["running"]:
            return JSONResponse(
                {"error": "A scrape is already running"},
                status_code=409,
            )
        _scrape_status["running"] = True
        _scrape_status["error"] = None
        _scrape_status["result"] = None

    def run_scrape():
        global _scrape_status
        try:
            from scheduler.runner import run_pipeline
            platforms_list = [platform] if platform else None
            result = run_pipeline(
                platforms=platforms_list,
                limit=limit,
                skip_analysis=False,
            )
            with _scrape_lock:
                _scrape_status["result"] = result
                _scrape_status["last_run"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            with _scrape_lock:
                _scrape_status["error"] = str(e)
        finally:
            with _scrape_lock:
                _scrape_status["running"] = False

    thread = threading.Thread(target=run_scrape, daemon=True)
    thread.start()

    return {"message": "Scrape started", "status": "running"}


@app.get("/api/scrape/status")
async def api_scrape_status():
    """Check current scrape status."""
    return _scrape_status


# ── User Actions (fav, approve, reject, notes) ─────────────────────
@app.get("/api/actions")
async def api_get_actions():
    """Get all user actions."""
    from db.reader import _get_connection
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM user_actions ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


@app.post("/api/actions")
async def api_save_action(
    item_id: str = Query(...),
    item_type: str = Query(...),
    action: str = Query(...),
    note: str = Query(None),
):
    """Save a user action (favorite, approve, reject, note)."""
    from db.reader import _get_connection
    conn = _get_connection()
    try:
        conn.execute("""
            INSERT INTO user_actions (item_id, item_type, action, note, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(item_id, item_type, action)
            DO UPDATE SET note = excluded.note, updated_at = datetime('now')
        """, (item_id, item_type, action, note))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/actions")
async def api_delete_action(
    item_id: str = Query(...),
    item_type: str = Query(...),
    action: str = Query(...),
):
    """Remove a user action."""
    from db.reader import _get_connection
    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM user_actions WHERE item_id = ? AND item_type = ? AND action = ?",
            (item_id, item_type, action),
        )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Tags ────────────────────────────────────────────────────────────
@app.get("/api/tags")
async def api_tags():
    """Get all unique tags from posts."""
    from db.reader import _get_connection
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT tags FROM posts WHERE tags IS NOT NULL AND tags != ''").fetchall()
        tag_counts = {}
        for row in rows:
            for tag in row["tags"].split(","):
                t = tag.strip()
                if t:
                    tag_counts[t] = tag_counts.get(t, 0) + 1
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"tag": t, "count": c} for t, c in sorted_tags]
    except Exception:
        return []


# ── Export ──────────────────────────────────────────────────────────
@app.get("/api/export")
async def api_export(format: str = Query("json")):
    """Export approved ideas as JSON or CSV."""
    from db.reader import _get_connection
    conn = _get_connection()
    try:
        # Get approved idea IDs
        approved_rows = conn.execute(
            "SELECT item_id FROM user_actions WHERE item_type = 'idea' AND action = 'approve'"
        ).fetchall()
        approved_ids = [str(r["item_id"]) for r in approved_rows]

        if not approved_ids:
            ideas_rows = conn.execute("SELECT * FROM app_ideas ORDER BY id DESC").fetchall()
        else:
            placeholders = ",".join("?" * len(approved_ids))
            ideas_rows = conn.execute(
                f"SELECT * FROM app_ideas WHERE id IN ({placeholders}) ORDER BY id DESC",
                approved_ids,
            ).fetchall()

        ideas = [dict(r) for r in ideas_rows]

        if format == "csv":
            import csv
            import io
            output = io.StringIO()
            if ideas:
                writer = csv.DictWriter(output, fieldnames=ideas[0].keys())
                writer.writeheader()
                writer.writerows(ideas)
            from starlette.responses import Response
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=pain_miner_export.csv"},
            )

        return ideas
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── User Notes (custom ideas / brainstorm) ─────────────────────────
@app.get("/api/notes")
async def api_get_notes():
    """Get all user notes."""
    from db.reader import _get_connection
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM user_notes ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


@app.post("/api/notes")
async def api_create_note(request: Request):
    """Create a new note."""
    from db.reader import _get_connection
    body = await request.json()
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO user_notes (title, content, tags) VALUES (?, ?, ?)",
            (body.get("title", ""), body.get("content", ""), body.get("tags", "")),
        )
        conn.commit()
        return {"ok": True, "id": cursor.lastrowid}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.put("/api/notes/{note_id}")
async def api_update_note(note_id: int, request: Request):
    """Update an existing note."""
    from db.reader import _get_connection
    body = await request.json()
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE user_notes SET title=?, content=?, tags=?, updated_at=datetime('now') WHERE id=?",
            (body.get("title", ""), body.get("content", ""), body.get("tags", ""), note_id),
        )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/notes/{note_id}")
async def api_delete_note(note_id: int):
    """Delete a note."""
    from db.reader import _get_connection
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM user_notes WHERE id=?", (note_id,))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Static frontend ────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend"


@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount static files AFTER specific routes
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


# ── Run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
