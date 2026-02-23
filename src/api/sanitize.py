"""HTML sanitization for LLM output before template rendering.

Uses nh3 to whitelist-sanitize HTML produced by the LLM, preventing
stored XSS while preserving safe formatting tags.
"""

import nh3

# Tags the LLM is allowed to produce for rich formatting
ALLOWED_TAGS = frozenset(
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
        "h5",
        "h6",
        "blockquote",
        "code",
        "pre",
        "span",
        "div",
        "a",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    }
)

# Attributes allowed on specific tags
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title"},
    "span": {"class"},
    "div": {"class"},
    "code": {"class"},
    "pre": {"class"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}


def sanitize_html(html: str) -> str:
    """Sanitize HTML string using nh3, allowing only safe tags and attributes.

    Strips script tags, event handlers (onclick, onload, etc.),
    dangerous attributes, and any tags not in the allowlist.

    Args:
        html: Raw HTML string from LLM output.

    Returns:
        Sanitized HTML string safe for rendering.
    """
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
    )
