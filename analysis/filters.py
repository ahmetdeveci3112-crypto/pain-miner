# analysis/filters.py — Pre-filtering posts for pain points

from config.config_loader import get_config, PROMPT_FILTER
from utils.helpers import sanitize_text
from utils.logger import setup_logger

log = setup_logger()


def format_post_content(post: dict) -> str:
    """Format post/comment content with appropriate context."""
    parent_body = post.get("parent_body", "")
    if parent_body:
        return (
            f"Post title: {post.get('title', '')}\n"
            f"Post body: {parent_body}\n"
            f"Comment: {post.get('body', '')}"
        )
    return f"Post title: {post.get('title', '')}\nPost body: {post.get('body', '')}"


def build_filter_prompt(post: dict) -> str:
    """Build the filter prompt for a single post."""
    config = get_config()
    prompt_template = config["prompts"].get(PROMPT_FILTER, "")
    content = format_post_content(post)

    return f"{prompt_template}\n\nPlatform: {post.get('platform', 'unknown')}\nSource: {post.get('source', '')}\n\n{content}"


def calculate_weighted_score(scores: dict) -> float:
    """Calculate weighted opportunity score from filter results."""
    config = get_config()
    weights = config["scoring"]

    return (
        scores.get("relevance_score", 0) * weights["relevance_weight"]
        + scores.get("emotional_intensity", 0) * weights["emotion_weight"]
        + scores.get("pain_point_clarity", 0) * weights["pain_point_weight"]
        + scores.get("implementability_score", 0) * weights["implementability_weight"]
        + scores.get("technical_depth_score", 0) * weights["technical_depth_weight"]
    )
