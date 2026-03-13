# analysis/insights.py — Deep insight extraction and app idea generation

from config.config_loader import get_config, PROMPT_INSIGHT, PROMPT_APP_IDEA
from analysis.filters import format_post_content
from utils.logger import setup_logger

log = setup_logger()


def build_insight_prompt(post: dict) -> str:
    """Build the deep insight prompt for a single post."""
    config = get_config()
    prompt_template = config["prompts"].get(PROMPT_INSIGHT, "")
    content = format_post_content(post)

    return f"{prompt_template}\n\nPlatform: {post.get('platform', 'unknown')}\nSource: {post.get('source', '')}\n\n{content}"


def build_app_idea_prompt(post: dict, insight: dict = None) -> str:
    """Build the app idea generation prompt from a problem."""
    config = get_config()
    prompt_template = config["prompts"].get(PROMPT_APP_IDEA, "")

    context = f"Problem: {post.get('title', '')}\nDetails: {post.get('body', '')}"

    if insight:
        context += f"\n\nPain Point: {insight.get('pain_point', '')}"
        context += f"\nAffected Audience: {insight.get('affected_audience', '')}"
        context += f"\nExisting Alternatives: {insight.get('existing_alternatives', '')}"
        context += f"\nProduct Opportunity: {insight.get('product_opportunity', '')}"

    return f"{prompt_template}\n\n{context}"
