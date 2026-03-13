# main.py — Pain Miner CLI entry point

import argparse
import json
import sys

from config.config_loader import get_config
from db.schema import create_tables
from db.reader import get_stats, get_top_insights, get_app_ideas
from scheduler.runner import run_pipeline
from utils.logger import setup_logger
from utils.helpers import ensure_directory_exists

log = setup_logger()


def cmd_scrape(args):
    """Run the scraping and analysis pipeline."""
    platforms = None
    if args.platform:
        platforms = [args.platform]

    result = run_pipeline(
        platforms=platforms,
        limit=args.limit,
        skip_analysis=args.no_analysis,
    )

    if result:
        print(f"\n✅ Done! Scraped {result['scraped']} posts, "
              f"found {result['insights']} insights, "
              f"generated {result['app_ideas']} app ideas "
              f"in {result['duration']:.1f}s")


def cmd_stats(args):
    """Show database statistics."""
    ensure_directory_exists("data")
    create_tables()
    stats = get_stats()

    print("\n📊 Pain Miner Statistics")
    print("=" * 40)
    print(f"  Total posts:     {stats.get('total_posts', 0)}")
    print(f"  Analyzed:        {stats.get('analyzed_posts', 0)}")
    print(f"  App ideas:       {stats.get('app_ideas', 0)}")
    print(f"  Total runs:      {stats.get('total_runs', 0)}")

    by_platform = stats.get("by_platform", {})
    if by_platform:
        print("\n  By Platform:")
        for platform, count in by_platform.items():
            print(f"    {platform}: {count}")


def cmd_top(args):
    """Show top insights."""
    ensure_directory_exists("data")
    create_tables()
    posts = get_top_insights(limit=args.count, platform=args.platform)

    if not posts:
        print("No insights found. Run 'python main.py scrape' first.")
        return

    print(f"\n🏆 Top {len(posts)} Problems")
    print("=" * 60)

    for i, post in enumerate(posts, 1):
        insight_data = {}
        if post.get("insight_data"):
            try:
                insight_data = json.loads(post["insight_data"])
            except:
                pass

        print(f"\n{i}. [{post.get('platform', '?').upper()}] {post.get('title', '')[:70]}")
        print(f"   Source: {post.get('source', '')} | ROI: {post.get('roi_weight', 0)} | Tags: {post.get('tags', '')}")
        print(f"   URL: {post.get('url', '')}")

        if insight_data.get("pain_point"):
            print(f"   Pain: {insight_data['pain_point'][:100]}")
        if insight_data.get("product_opportunity"):
            print(f"   Opportunity: {insight_data['product_opportunity'][:100]}")


def cmd_ideas(args):
    """Show generated app ideas."""
    ensure_directory_exists("data")
    create_tables()
    ideas = get_app_ideas(limit=args.count)

    if not ideas:
        print("No app ideas found. Run 'python main.py scrape' first.")
        return

    print(f"\n💡 App Ideas ({len(ideas)})")
    print("=" * 60)

    for i, idea in enumerate(ideas, 1):
        strategy_emoji = "📈" if idea.get("strategy") == "traffic" else "💰"
        print(f"\n{strategy_emoji} {i}. {idea.get('app_name', 'N/A')} ({idea.get('app_type', '')})")
        print(f"   {idea.get('description', '')[:100]}")
        print(f"   Target: {idea.get('target_audience', '')[:80]}")
        print(f"   Monetization: {idea.get('monetization', '')[:80]}")
        print(f"   Complexity: {idea.get('complexity', '')} | "
              f"Traffic: {idea.get('traffic_potential', '')} | "
              f"Revenue: {idea.get('revenue_potential', '')}")
        print(f"   Tech: {idea.get('tech_stack', '')[:80]}")
        print(f"   From: [{idea.get('platform', '')}] {idea.get('post_title', '')[:60]}")

        mvp = idea.get("mvp_features", "")
        if mvp:
            try:
                features = json.loads(mvp) if isinstance(mvp, str) else mvp
                if isinstance(features, list):
                    print(f"   MVP Features:")
                    for f in features[:5]:
                        print(f"     • {f}")
            except:
                pass


def cmd_init(args):
    """Initialize the database."""
    ensure_directory_exists("data")
    create_tables()
    print("✅ Database initialized at data/pain_miner.db")


def main():
    parser = argparse.ArgumentParser(
        description="🔍 Pain Miner — AI Problem Hunter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py init                           Initialize database
  python main.py scrape                         Scrape all platforms + analyze
  python main.py scrape --platform hackernews   Scrape only Hacker News
  python main.py scrape --limit 10              Limit to 10 posts per platform
  python main.py scrape --no-analysis           Scrape only, skip AI analysis
  python main.py stats                          Show database statistics
  python main.py top                            Show top problems
  python main.py top --count 5                  Show top 5 problems
  python main.py ideas                          Show generated app ideas
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize the database")

    # scrape
    scrape_parser = subparsers.add_parser("scrape", help="Run scraping pipeline")
    scrape_parser.add_argument(
        "--platform", choices=["reddit", "hackernews", "producthunt"],
        help="Scrape only a specific platform",
    )
    scrape_parser.add_argument(
        "--limit", type=int, help="Max items per platform",
    )
    scrape_parser.add_argument(
        "--no-analysis", action="store_true",
        help="Skip AI analysis, only scrape",
    )

    # stats
    stats_parser = subparsers.add_parser("stats", help="Show statistics")

    # top
    top_parser = subparsers.add_parser("top", help="Show top problems")
    top_parser.add_argument("--count", "-n", type=int, default=20)
    top_parser.add_argument("--platform", choices=["reddit", "hackernews", "producthunt"])

    # ideas
    ideas_parser = subparsers.add_parser("ideas", help="Show app ideas")
    ideas_parser.add_argument("--count", "-n", type=int, default=50)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "init": cmd_init,
        "scrape": cmd_scrape,
        "stats": cmd_stats,
        "top": cmd_top,
        "ideas": cmd_ideas,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
