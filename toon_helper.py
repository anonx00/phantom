"""
TOON Helper - Token-Oriented Object Notation for efficient LLM prompts

Custom implementation of TOON format to reduce tokens sent to Gemini by ~40%.
The official toon-format PyPI package is just a placeholder with no implementation.

TOON Format Example:
  articles[3]{title,source,url}:
    AI Breakthrough,TechCrunch,https://...
    Crypto Update,CoinDesk,https://...
    News Item,TheVerge,https://...

This is ~40% fewer tokens than equivalent JSON.
Reference: https://github.com/toon-format/toon
"""

import logging
import json
import re
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

TOON_AVAILABLE = True  # Our implementation is always available


def _escape_toon_value(value: Any) -> str:
    """Escape a value for TOON format."""
    if value is None:
        return ""
    s = str(value)
    # Escape commas and newlines
    s = s.replace("\\", "\\\\")
    s = s.replace(",", "\\,")
    s = s.replace("\n", "\\n")
    return s


def _encode_list_of_dicts(data: List[Dict], key: str) -> str:
    """Encode a list of dicts in TOON table format."""
    if not data:
        return f"{key}[0]{{}}:"

    # Get all unique keys from first item (assumes uniform structure)
    fields = list(data[0].keys())

    # Build header
    header = f"{key}[{len(data)}]{{{','.join(fields)}}}:"

    # Build rows
    rows = []
    for item in data:
        values = [_escape_toon_value(item.get(f, "")) for f in fields]
        rows.append("  " + ",".join(values))

    return header + "\n" + "\n".join(rows)


def _encode_dict(data: Dict, indent: int = 0) -> str:
    """Encode a dict in TOON format."""
    lines = []
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            # List of dicts - use table format
            lines.append(prefix + _encode_list_of_dicts(value, key))
        elif isinstance(value, list):
            # Simple list
            escaped = [_escape_toon_value(v) for v in value]
            lines.append(f"{prefix}{key}[{len(value)}]:{','.join(escaped)}")
        elif isinstance(value, dict):
            # Nested dict
            lines.append(f"{prefix}{key}{{}}:")
            lines.append(_encode_dict(value, indent + 1))
        else:
            # Simple value
            lines.append(f"{prefix}{key}:{_escape_toon_value(value)}")

    return "\n".join(lines)


def encode_for_llm(data: Any, use_toon: bool = True) -> str:
    """
    Encode data for LLM input using TOON format.

    TOON saves ~40% tokens on structured data like:
    - News article lists
    - Trend data
    - Memory/context

    Args:
        data: Any JSON-serializable data
        use_toon: Whether to use TOON (default True)

    Returns:
        Encoded string (TOON or JSON)
    """
    if not use_toon:
        return json.dumps(data, separators=(',', ':'))

    try:
        if isinstance(data, dict):
            encoded = _encode_dict(data)
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            encoded = _encode_list_of_dicts(data, "items")
        elif isinstance(data, list):
            escaped = [_escape_toon_value(v) for v in data]
            encoded = f"items[{len(data)}]:{','.join(escaped)}"
        else:
            encoded = str(data)

        return f"```toon\n{encoded}\n```"
    except Exception as e:
        logger.warning(f"TOON encoding failed, using JSON: {e}")
        return json.dumps(data, separators=(',', ':'))


def _unescape_toon_value(value: str) -> str:
    """Unescape a TOON value."""
    value = value.replace("\\n", "\n")
    value = value.replace("\\,", ",")
    value = value.replace("\\\\", "\\")
    return value


def _parse_toon_table(header: str, rows: List[str]) -> List[Dict]:
    """Parse a TOON table back to list of dicts."""
    # Parse header: key[count]{field1,field2,...}:
    match = re.match(r'(\w+)\[(\d+)\]\{([^}]*)\}:', header)
    if not match:
        return []

    fields = match.group(3).split(',')
    result = []

    for row in rows:
        row = row.strip()
        if not row:
            continue

        # Split by unescaped commas
        values = re.split(r'(?<!\\),', row)
        item = {}
        for i, field in enumerate(fields):
            if i < len(values):
                item[field] = _unescape_toon_value(values[i])
            else:
                item[field] = ""
        result.append(item)

    return result


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
        match = re.search(r'```toon\n(.*?)\n```', text, re.DOTALL)
        if match:
            try:
                toon_content = match.group(1)
                return _decode_toon(toon_content)
            except Exception as e:
                logger.warning(f"TOON decode failed: {e}")

    # Try JSON
    try:
        json_match = re.search(r'\{.*\}|\[.*\]', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass

    return text


def _decode_toon(content: str) -> Dict:
    """Decode TOON content to dict."""
    result = {}
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Check for table format: key[count]{fields}:
        table_match = re.match(r'(\w+)\[(\d+)\]\{([^}]*)\}:', line)
        if table_match:
            key = table_match.group(1)
            count = int(table_match.group(2))
            # Collect next 'count' rows
            rows = []
            for j in range(i + 1, min(i + 1 + count, len(lines))):
                if lines[j].strip():
                    rows.append(lines[j])
            result[key] = _parse_toon_table(line, rows)
            i += 1 + count
            continue

        # Check for simple list: key[count]:value1,value2,...
        list_match = re.match(r'(\w+)\[(\d+)\]:(.*)', line)
        if list_match:
            key = list_match.group(1)
            values = re.split(r'(?<!\\),', list_match.group(3))
            result[key] = [_unescape_toon_value(v) for v in values]
            i += 1
            continue

        # Check for simple key:value
        kv_match = re.match(r'(\w+):(.*)', line)
        if kv_match:
            key = kv_match.group(1)
            value = _unescape_toon_value(kv_match.group(2))
            # Try to parse as number
            try:
                if '.' in value:
                    result[key] = float(value)
                else:
                    result[key] = int(value)
            except ValueError:
                result[key] = value
            i += 1
            continue

        i += 1

    return result


def encode_news_for_prompt(articles: List[Dict]) -> str:
    """
    Encode news articles for LLM prompt using TOON.

    Example output:
    ```toon
    articles[3]{title,source,summary,url}:
      AI Breakthrough,TechCrunch,New model achieves...,https://...
      Crypto Update,CoinDesk,Bitcoin reaches...,https://...
      Startup News,TheVerge,New unicorn...,https://...
    ```
    """
    if not articles:
        return "No articles available."

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
    """Encode Twitter mentions for LLM prompt using TOON."""
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
    """Encode trending topics for LLM prompt using TOON."""
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
    """Encode memory/context for LLM prompt using TOON."""
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
