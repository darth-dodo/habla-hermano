"""HTML sanitization for LLM output before template rendering.

Uses nh3 to whitelist-sanitize HTML produced by the LLM, preventing
stored XSS while preserving safe formatting tags.
"""

import re

import markdown
import nh3

# Tags the LLM is allowed to produce for rich formatting
ALLOWED_TAGS: set[str] = {
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


def _ensure_list_blank_lines(text: str) -> str:
    """Insert a blank line before list blocks not preceded by one.

    Python's markdown library requires a blank line before list items.
    LLMs often omit this, producing output like:

        Here are words:
        - hola
        - gracias

    This preprocessor inserts the blank line before the first item of
    each contiguous list block, without affecting items within the block.
    """
    lines = text.split("\n")
    result: list[str] = []
    list_pattern = re.compile(r"^[ \t]*(?:[-*+]|\d+\.)[ \t]")
    for i, line in enumerate(lines):
        if list_pattern.match(line) and i > 0:
            prev = lines[i - 1]
            if prev.strip() and not list_pattern.match(prev):
                result.append("")
        result.append(line)
    return "\n".join(result)


def render_markdown(text: str) -> str:
    """Convert Markdown text to sanitized HTML.

    Preprocesses to fix common LLM markdown issues (missing blank lines
    before lists), renders to HTML with fenced_code and tables extensions,
    then pipes through nh3 sanitization to strip unsafe tags.

    Args:
        text: Raw Markdown string.

    Returns:
        Sanitized HTML string safe for rendering.
    """
    text = _ensure_list_blank_lines(text)
    html = markdown.markdown(text, extensions=["fenced_code", "tables"])
    return sanitize_html(html)
