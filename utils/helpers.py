# utils/helpers.py

import os
import json
import re
from datetime import datetime, timedelta, timezone


def ensure_directory_exists(path: str):
    """Create a directory if it does not exist."""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def save_json(data: dict, filename: str):
    """Save dictionary as a JSON file."""
    ensure_directory_exists(os.path.dirname(filename))
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(filename: str) -> dict:
    """Load dictionary from JSON file."""
    if not os.path.exists(filename):
        return {}
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def format_datetime(dt: datetime = None) -> str:
    """Return timezone-aware datetime in ISO 8601 format (UTC)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.isoformat()


def days_ago(days: int) -> datetime:
    """Return timezone-aware datetime for N days ago."""
    return datetime.now(timezone.utc) - timedelta(days=days)


def truncate(text: str, max_chars: int = 1000) -> str:
    """Truncate a string to fit within a character limit."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def sanitize_text(text: str) -> str:
    """Remove some emojis and non-printable unicode characters."""
    if not isinstance(text, str):
        return ""
    emoji_pattern = re.compile("[\U00010000-\U0010FFFF]", flags=re.UNICODE)
    return emoji_pattern.sub("", text).strip()


def extract_json_from_text(text: str) -> str:
    """Extract JSON payload from markdown-fenced or plain text."""
    if not text:
        return text

    stripped = text.strip()

    # Fenced block
    match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?```", stripped, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1).strip()

    # First object/array fallback
    match = re.search(r"[\{\[].*[\}\]]", stripped, re.DOTALL)
    if match:
        return match.group(0).strip()

    return stripped


def matches_problem_pattern(text: str, patterns: list[str]) -> bool:
    """Check if text contains any of the problem patterns."""
    text_lower = text.lower()
    return any(pattern.lower() in text_lower for pattern in patterns)
