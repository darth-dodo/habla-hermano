"""Shared utilities for agent nodes."""

from __future__ import annotations

import json
from typing import Any


def extract_json_from_response(content: str) -> dict[str, Any]:
    """Extract and parse JSON from an LLM response that may be wrapped in markdown.

    Handles responses like:
        ```json
        {"key": "value"}
        ```

    Args:
        content: Raw LLM response string.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        json.JSONDecodeError: If the content cannot be parsed as JSON.
    """
    if "```json" in content:
        content = content.split("```json", maxsplit=1)[1].split("```", maxsplit=1)[0]
    elif "```" in content:
        content = content.split("```", maxsplit=1)[1].split("```", maxsplit=1)[0]

    result: dict[str, Any] = json.loads(content.strip())
    return result
