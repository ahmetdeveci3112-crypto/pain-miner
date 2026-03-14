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

    platform = post.get('platform', 'unknown')
    context = f"Platform: {platform}\nSource: {post.get('source', '')}\n"
    context += f"Problem: {post.get('title', '')}\nDetails: {post.get('body', '')}"

    # Add PH context to trigger creative optimization
    if platform == "producthunt":
        context += "\n\n⚠️ Bu kaynak Product Hunt'tan geliyor — bu, benzer bir uygulama zaten mevcut demektir. Fikri yaratıcı bir şekilde farklılaştır, birebir kopyalama!"

    if insight:
        context += f"\n\nAcı Noktası: {insight.get('pain_point', '')}"
        context += f"\nEtkilenen Kitle: {insight.get('affected_audience', '')}"
        context += f"\nMevcut Alternatifler: {insight.get('existing_alternatives', '')}"
        context += f"\nÜrün Fırsatı: {insight.get('product_opportunity', '')}"

    return f"{prompt_template}\n\n{context}"
