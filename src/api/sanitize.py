"""HTML sanitization for LLM output rendered with Jinja2's ``| safe`` filter.

Uses nh3 (Rust-based) for fast, allowlist-based HTML sanitization.
Only tags appropriate for language-learning content are permitted.
"""

from __future__ import annotations

import nh3

# Tags commonly produced by the LLM for formatted lesson/chat content.
ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "p",
        "br",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "span",
        "div",
        "blockquote",
        "code",
        "pre",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "details",
        "summary",
        "hr",
    }
)

# Only safe, presentation-oriented attributes.
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "*": {"class", "id"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}


def sanitize_html(html: str) -> str:
    """Sanitize HTML using an allowlist of safe tags and attributes.

    Strips ``<script>``, ``<iframe>``, event handlers, and any other
    potentially dangerous markup while preserving formatting tags that
    the LLM legitimately uses for lesson content.

    Args:
        html: Raw HTML string (typically from LLM output).

    Returns:
        Sanitized HTML string safe for rendering with ``| safe``.
    """
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
    )
