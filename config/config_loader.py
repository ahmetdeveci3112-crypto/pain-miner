# config/config_loader.py

import yaml
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
PROMPT_PATH = PROJECT_ROOT / "analysis" / "prompts"

# Prompt template constants
PROMPT_FILTER = "filter"
PROMPT_INSIGHT = "insight"
PROMPT_APP_IDEA = "app_idea"
PROMPT_COMMUNITY_DISCOVERY = "community_discovery"
PROMPT_COMMUNITY_DISCOVERY_SYSTEM = "community_discovery_system"
PROMPTS_ALL = [
    PROMPT_FILTER, PROMPT_INSIGHT, PROMPT_APP_IDEA,
    PROMPT_COMMUNITY_DISCOVERY, PROMPT_COMMUNITY_DISCOVERY_SYSTEM,
]

_config_cache = None


def get_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    with open(CONFIG_PATH, "r") as f:
        raw_config = yaml.safe_load(f)

    # Inject secrets from environment
    raw_config["reddit"] = {
        "client_id": os.getenv("REDDIT_CLIENT_ID"),
        "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
        "user_agent": os.getenv("REDDIT_USER_AGENT", "pain-miner:v1.0 (by /u/painminer)"),
        "username": os.getenv("REDDIT_USERNAME"),
        "password": os.getenv("REDDIT_PASSWORD"),
    }

    raw_config["gemini"] = {
        "api_key": os.getenv("GEMINI_API_KEY"),
    }

    # Inject prompts
    raw_config["prompts"] = load_all_prompts()

    # Store project root for path resolution
    raw_config["_project_root"] = str(PROJECT_ROOT)

    _config_cache = raw_config
    return raw_config


def load_all_prompts() -> dict:
    """Load all prompt templates from the prompts directory."""
    prompts = {}
    for key in PROMPTS_ALL:
        path = PROMPT_PATH / f"{key}.txt"
        try:
            with open(path, "r", encoding="utf-8") as f:
                prompts[key] = f.read().strip()
        except FileNotFoundError:
            prompts[key] = ""
    return prompts


def get_project_root() -> Path:
    return PROJECT_ROOT
