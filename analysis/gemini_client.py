# analysis/gemini_client.py — Google Gemini API client

from typing import Optional, List, Tuple
import json
import time
from google import genai
from google.genai import types

from utils.logger import setup_logger
from utils.helpers import extract_json_from_text
from config.config_loader import get_config

log = setup_logger()

_client = None


def get_client():
    """Get or create Gemini API client."""
    global _client
    if _client is None:
        config = get_config()
        api_key = config["gemini"]["api_key"]
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")
        _client = genai.Client(api_key=api_key)
    return _client


def analyze_with_gemini(prompt: str, system_prompt: str = None,
                        retries: int = 5) -> Optional[dict]:
    """Send a prompt to Gemini and parse JSON response."""
    client = get_client()
    config = get_config()
    model = config["ai"]["model"]

    contents = prompt
    generate_config = types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=2048,
        response_mime_type="application/json",
    )

    if system_prompt:
        generate_config.system_instruction = system_prompt

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=generate_config,
            )

            text = response.text
            if not text:
                log.warning(f"Empty response from Gemini (attempt {attempt + 1})")
                continue

            # Parse JSON
            json_str = extract_json_from_text(text)
            result = json.loads(json_str)
            return result

        except json.JSONDecodeError as e:
            log.warning(f"JSON parse error (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(1)
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "resource" in error_msg.lower():
                wait = (attempt + 1) * 10
                log.warning(f"Rate limited. Waiting {wait}s... (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
            else:
                log.error(f"Gemini API error (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    time.sleep(3)

    return None


def batch_analyze(items: List[dict], prompt_builder, system_prompt: str = None,
                  delay: float = 3.0) -> List[Tuple[str, Optional[dict]]]:
    """Analyze a batch of items sequentially with rate limiting.

    Args:
        items: List of dicts with at least an 'id' key.
        prompt_builder: Function that takes an item dict and returns a prompt string.
        system_prompt: Optional system prompt.
        delay: Delay between API calls in seconds.

    Returns:
        List of (item_id, result_dict_or_None) tuples.
    """
    results = []
    total = len(items)

    for i, item in enumerate(items, 1):
        log.info(f"Analyzing {i}/{total}: {item.get('title', item['id'])[:60]}")

        prompt = prompt_builder(item)
        result = analyze_with_gemini(prompt, system_prompt)

        results.append((item["id"], result))

        if i < total:
            time.sleep(delay)

    return results
