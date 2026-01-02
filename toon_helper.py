"""
TOON Helper - Token-Oriented Object Notation for efficient LLM prompts

Uses TOON format to reduce tokens sent to Gemini by ~40%.
This saves money on API calls while maintaining data accuracy.

Reference: https://github.com/toon-format/toon
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import toon, fall back to JSON if not available
# Note: toon-format package doesn't have a stable release yet
# JSON fallback is the default and works fine
try:
    from toon_format import encode as toon_encode, decode as toon_decode
    TOON_AVAILABLE = True
except ImportError:
    TOON_AVAILABLE = False
    # JSON fallback is expected and silent - no warning needed


def encode_for_llm(data: Any, use_toon: bool = True) -> str:
    """
    Encode data for LLM input using TOON format.
    Falls back to compact JSON if TOON not available.

    TOON saves ~40% tokens on structured data like:
    - News article lists
    - User mentions/replies
    - Trend data
    - Memory/context

    Args:
        data: Any JSON-serializable data
        use_toon: Whether to use TOON (default True)

    Returns:
        Encoded string (TOON or JSON)
    """
    if use_toon and TOON_AVAILABLE:
        try:
            encoded = toon_encode(data)
            return f"```toon\n{encoded}\n```"
        except Exception as e:
            logger.warning(f"TOON encoding failed, using JSON: {e}")

    # Fallback to compact JSON
    import json
    return json.dumps(data, separators=(',', ':'))


def decode_from_llm(text: str) -> Any:
    """
    Decode TOON or JSON from LLM output.

    Args:
        text: Encoded string (TOON or JSON)

    Returns:
        Decoded data
    """
    # Check for TOON code block
    if "```toon" in text:
        # Extract TOON content
        import re
        match = re.search(r'```toon\n(.*?)\n```', text, re.DOTALL)
        if match and TOON_AVAILABLE:
            try:
                return toon_decode(match.group(1))
            except Exception as e:
                logger.warning(f"TOON decode failed: {e}")

    # Try JSON
    import json
    try:
        # Find JSON in text
        import re
        json_match = re.search(r'\{.*\}|\[.*\]', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass

    return text


def encode_news_for_prompt(articles: List[Dict]) -> str:
    """
    Encode news articles for LLM prompt using TOON.

    Example output (TOON):
    ```toon
    articles[3]{title,source,summary,url}:
      AI Breakthrough,TechCrunch,New model achieves...,https://...
      Crypto Update,CoinDesk,Bitcoin reaches...,https://...
      Startup News,TheVerge,New unicorn...,https://...
    ```

    This is ~50% fewer tokens than JSON for article lists.
    """
    if not articles:
        return "No articles available."

    # Simplify articles for encoding
    simplified = []
    for a in articles:
        simplified.append({
            "title": a.get("title", "")[:100],
            "source": a.get("source", "unknown"),
            "summary": a.get("summary", a.get("context", ""))[:200],
            "url": a.get("url", "")
        })

    return encode_for_llm({"articles": simplified})


def encode_mentions_for_prompt(mentions: List[Dict]) -> str:
    """
    Encode Twitter mentions for LLM prompt using TOON.

    Saves tokens when AI is deciding which mentions to reply to.
    """
    if not mentions:
        return "No mentions to process."

    simplified = []
    for m in mentions:
        simplified.append({
            "author": m.get("author", "unknown"),
            "text": m.get("text", "")[:280],
            "tweet_id": m.get("tweet_id", ""),
        })

    return encode_for_llm({"mentions": simplified})


def encode_trends_for_prompt(trends: List[Dict]) -> str:
    """
    Encode trending topics for LLM prompt using TOON.
    """
    if not trends:
        return "No trends available."

    simplified = []
    for t in trends:
        simplified.append({
            "topic": t.get("name", t.get("topic", "")),
            "volume": t.get("tweet_volume", t.get("volume", 0)),
            "category": t.get("category", "general"),
        })

    return encode_for_llm({"trends": simplified})


def encode_memory_for_prompt(memories: List[Dict]) -> str:
    """
    Encode memory/context for LLM prompt using TOON.

    Used to provide AI with context about past interactions.
    """
    if not memories:
        return "No previous context."

    simplified = []
    for m in memories:
        simplified.append({
            "type": m.get("type", "post"),
            "content": m.get("content", "")[:200],
            "timestamp": m.get("timestamp", ""),
            "engagement": m.get("engagement", 0),
        })

    return encode_for_llm({"memory": simplified})


# Convenience function for general use
def toon(data: Any) -> str:
    """Shorthand for encode_for_llm with TOON."""
    return encode_for_llm(data, use_toon=True)
