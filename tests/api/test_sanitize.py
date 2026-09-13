"""Tests for src/api/sanitize.py — HTML sanitization of LLM output.

Validates that dangerous HTML (script tags, event handlers, iframes) is
stripped while safe formatting tags are preserved.  Also verifies the
Jinja2 ``sanitize`` filter is registered on the template environment.
Also covers _ensure_list_blank_lines and render_markdown, plus
unsign_json_cookie from src/api/cookies.py.
"""

from unittest.mock import patch

import markupsafe

from src.api.cookies import _get_serializer, sign_cookie_value, unsign_json_cookie
from src.api.sanitize import _ensure_list_blank_lines, render_markdown, sanitize_html
from src.config import Settings

# =============================================================================
# Unit Tests: sanitize_html — dangerous content stripping
# =============================================================================


class TestSanitizeHtmlStripsDangerousContent:
    """Verify that script tags, event handlers, and other XSS vectors are removed."""

    def test_strips_script_tags(self) -> None:
        """Script tags and their content must be completely removed."""
        html = '<p>Hello</p><script>alert("xss")</script>'
        result = sanitize_html(html)
        assert "<script>" not in result
        assert "alert" not in result
        assert "<p>Hello</p>" in result

    def test_strips_script_tags_with_src(self) -> None:
        """Script tags with src attributes must be removed."""
        html = '<script src="https://evil.com/xss.js"></script><p>Safe</p>'
        result = sanitize_html(html)
        assert "<script" not in result
        assert "<p>Safe</p>" in result

    def test_strips_onload_event_handler(self) -> None:
        """The onload event handler attribute must be removed."""
        html = '<img onload="alert(1)" src="x.png">'
        result = sanitize_html(html)
        assert "onload" not in result

    def test_strips_onclick_event_handler(self) -> None:
        """The onclick event handler attribute must be removed."""
        html = '<div onclick="stealCookies()">Click me</div>'
        result = sanitize_html(html)
        assert "onclick" not in result
        assert "Click me" in result

    def test_strips_onerror_event_handler(self) -> None:
        """The onerror event handler must be removed."""
        html = '<img onerror="alert(1)" src="invalid">'
        result = sanitize_html(html)
        assert "onerror" not in result

    def test_strips_onmouseover_event_handler(self) -> None:
        """The onmouseover event handler must be removed."""
        html = '<span onmouseover="steal()">hover</span>'
        result = sanitize_html(html)
        assert "onmouseover" not in result
        assert "hover" in result

    def test_strips_iframe_tags(self) -> None:
        """Iframe tags must be removed entirely."""
        html = '<p>Before</p><iframe src="https://evil.com"></iframe><p>After</p>'
        result = sanitize_html(html)
        assert "<iframe" not in result
        assert "<p>Before</p>" in result
        assert "<p>After</p>" in result

    def test_strips_style_attribute(self) -> None:
        """Inline style attributes should be removed to prevent CSS injection."""
        html = '<div style="background:url(javascript:alert(1))">content</div>'
        result = sanitize_html(html)
        assert "style=" not in result
        assert "content" in result

    def test_strips_javascript_href(self) -> None:
        """Links with javascript: protocol should be sanitized."""
        html = '<a href="javascript:alert(1)">click</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result


# =============================================================================
# Unit Tests: sanitize_html — allowed tags preserved
# =============================================================================


class TestSanitizeHtmlPreservesAllowedTags:
    """Verify that safe formatting tags pass through sanitization intact."""

    def test_preserves_paragraph_tags(self) -> None:
        """Paragraph tags must be preserved."""
        html = "<p>Hello world</p>"
        assert sanitize_html(html) == "<p>Hello world</p>"

    def test_preserves_strong_tags(self) -> None:
        """Strong/bold tags must be preserved."""
        html = "<strong>important</strong>"
        assert sanitize_html(html) == "<strong>important</strong>"

    def test_preserves_em_tags(self) -> None:
        """Emphasis tags must be preserved."""
        html = "<em>emphasized</em>"
        assert sanitize_html(html) == "<em>emphasized</em>"

    def test_preserves_unordered_lists(self) -> None:
        """Unordered list tags must be preserved."""
        html = "<ul><li>item one</li><li>item two</li></ul>"
        result = sanitize_html(html)
        assert "<ul>" in result
        assert "<li>item one</li>" in result
        assert "<li>item two</li>" in result

    def test_preserves_ordered_lists(self) -> None:
        """Ordered list tags must be preserved."""
        html = "<ol><li>first</li><li>second</li></ol>"
        result = sanitize_html(html)
        assert "<ol>" in result
        assert "<li>first</li>" in result

    def test_preserves_heading_tags(self) -> None:
        """Heading tags (h1-h6) must be preserved."""
        html = "<h1>Title</h1><h2>Subtitle</h2><h3>Section</h3>"
        result = sanitize_html(html)
        assert "<h1>Title</h1>" in result
        assert "<h2>Subtitle</h2>" in result
        assert "<h3>Section</h3>" in result

    def test_preserves_code_and_pre_tags(self) -> None:
        """Code and pre tags must be preserved for technical content."""
        html = '<pre><code class="python">print("hello")</code></pre>'
        result = sanitize_html(html)
        assert "<pre>" in result
        assert "<code" in result

    def test_preserves_blockquote(self) -> None:
        """Blockquote tags must be preserved."""
        html = "<blockquote>A wise quote</blockquote>"
        assert sanitize_html(html) == "<blockquote>A wise quote</blockquote>"

    def test_preserves_br_tags(self) -> None:
        """Line break tags must be preserved."""
        html = "Line one<br>Line two"
        result = sanitize_html(html)
        assert "<br>" in result

    def test_preserves_anchor_with_href(self) -> None:
        """Anchor tags with safe href attributes must be preserved."""
        html = '<a href="https://example.com" title="Example">link</a>'
        result = sanitize_html(html)
        assert "<a " in result
        assert 'href="https://example.com"' in result

    def test_preserves_table_tags(self) -> None:
        """Table-related tags must be preserved."""
        html = "<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td>Cell</td></tr></tbody></table>"
        result = sanitize_html(html)
        assert "<table>" in result
        assert "<th>Header</th>" in result
        assert "<td>Cell</td>" in result

    def test_preserves_complex_nested_html(self) -> None:
        """Complex nested HTML with mixed allowed tags must be preserved."""
        html = "<div><p><strong>Bold</strong> and <em>italic</em></p><ul><li>Item</li></ul></div>"
        result = sanitize_html(html)
        assert "<strong>Bold</strong>" in result
        assert "<em>italic</em>" in result
        assert "<li>Item</li>" in result


# =============================================================================
# Unit Tests: sanitize_html — edge cases
# =============================================================================


class TestSanitizeHtmlEdgeCases:
    """Verify behavior with empty input, plain text, and mixed content."""

    def test_empty_string(self) -> None:
        """Empty string input should return empty string."""
        assert sanitize_html("") == ""

    def test_plain_text_passthrough(self) -> None:
        """Plain text without HTML tags should pass through unchanged."""
        text = "Hola, como estas?"
        assert sanitize_html(text) == text

    def test_mixed_safe_and_unsafe_content(self) -> None:
        """Safe tags preserved while unsafe tags stripped in mixed content."""
        html = "<p>Safe</p><script>evil()</script><strong>Also safe</strong>"
        result = sanitize_html(html)
        assert "<p>Safe</p>" in result
        assert "<strong>Also safe</strong>" in result
        assert "<script>" not in result
        assert "evil" not in result


# =============================================================================
# Unit Tests: _ensure_list_blank_lines — list preprocessing
# =============================================================================


class TestEnsureListBlankLines:
    """Verify that blank lines are inserted before list blocks when missing."""

    def test_paragraph_then_unordered_list_dash(self) -> None:
        """A paragraph followed directly by a - list should get a blank line inserted."""
        text = "Here are words:\n- hola\n- gracias"
        result = _ensure_list_blank_lines(text)
        assert result == "Here are words:\n\n- hola\n- gracias"

    def test_paragraph_then_ordered_list(self) -> None:
        """A paragraph followed directly by a numbered list should get a blank line."""
        text = "Steps to follow:\n1. First step\n2. Second step"
        result = _ensure_list_blank_lines(text)
        assert result == "Steps to follow:\n\n1. First step\n2. Second step"

    def test_already_has_blank_line_before_list(self) -> None:
        """If a blank line already precedes the list, no extra line should be added."""
        text = "Here are words:\n\n- hola\n- gracias"
        result = _ensure_list_blank_lines(text)
        assert result == text

    def test_consecutive_list_items_no_extra_blanks(self) -> None:
        """Consecutive list items should not get blank lines inserted between them."""
        text = "Items:\n- one\n- two\n- three"
        result = _ensure_list_blank_lines(text)
        # Only one blank line should be inserted (before - one)
        assert result == "Items:\n\n- one\n- two\n- three"

    def test_asterisk_list_marker(self) -> None:
        """A * list marker should also trigger blank line insertion."""
        text = "Words:\n* hola\n* adios"
        result = _ensure_list_blank_lines(text)
        assert result == "Words:\n\n* hola\n* adios"

    def test_plus_list_marker(self) -> None:
        """A + list marker should also trigger blank line insertion."""
        text = "Words:\n+ hola\n+ adios"
        result = _ensure_list_blank_lines(text)
        assert result == "Words:\n\n+ hola\n+ adios"

    def test_list_at_start_of_text(self) -> None:
        """A list at the very start of text (i=0) should not insert a blank line."""
        text = "- first\n- second"
        result = _ensure_list_blank_lines(text)
        assert result == "- first\n- second"

    def test_multiple_list_blocks(self) -> None:
        """Multiple separate list blocks each get a blank line when needed."""
        text = "Group 1:\n- a\n- b\nGroup 2:\n1. x\n2. y"
        result = _ensure_list_blank_lines(text)
        assert "Group 1:\n\n- a\n- b" in result
        assert "Group 2:\n\n1. x\n2. y" in result

    def test_render_markdown_end_to_end_list_without_blank(self) -> None:
        """render_markdown should convert list-without-blank-line to proper HTML."""
        text = "Here are words:\n- hola\n- gracias"
        html = render_markdown(text)
        assert "<ul>" in html
        assert "<li>" in html
        assert "hola" in html
        assert "gracias" in html


# =============================================================================
# Unit Tests: unsign_json_cookie — cookie verification
# =============================================================================


class TestUnsignJsonCookie:
    """Tests for unsign_json_cookie from src/api/cookies."""

    def _make_settings(self) -> Settings:
        """Create test settings for cookie signing."""
        return Settings(
            _env_file=None,  # type: ignore[call-arg]
            OPENROUTER_API_KEY="test-key",  # pragma: allowlist secret
            SECRET_KEY="test-cookie-secret",  # pragma: allowlist secret
            DEBUG=True,
        )

    def test_none_raw_value_returns_none(self) -> None:
        """unsign_json_cookie with None should return None."""
        with patch("src.api.cookies.get_settings", return_value=self._make_settings()):
            result = unsign_json_cookie(None)
            assert result is None

    def test_empty_string_returns_none(self) -> None:
        """unsign_json_cookie with empty string should return None."""
        with patch("src.api.cookies.get_settings", return_value=self._make_settings()):
            result = unsign_json_cookie("")
            assert result is None

    def test_tampered_signature_returns_none(self) -> None:
        """unsign_json_cookie with tampered data should return None."""
        settings = self._make_settings()
        with patch("src.api.cookies.get_settings", return_value=settings):
            signed = sign_cookie_value({"user": "test"})
            # Tamper with the signed value
            tampered = signed[:-5] + "XXXXX"
            result = unsign_json_cookie(tampered)
            assert result is None

    def test_non_dict_payload_returns_none(self) -> None:
        """unsign_json_cookie with a signed non-dict payload should return None."""
        settings = self._make_settings()
        with patch("src.api.cookies.get_settings", return_value=settings):
            # Directly sign a string value (not a dict)
            serializer = _get_serializer()
            signed_string = serializer.dumps("just-a-string")
            result = unsign_json_cookie(signed_string)
            assert result is None

    def test_valid_dict_payload_roundtrips(self) -> None:
        """unsign_json_cookie with a valid signed dict should return the dict."""
        settings = self._make_settings()
        with patch("src.api.cookies.get_settings", return_value=settings):
            original = {"session_id": "abc123", "score": 42}
            signed = sign_cookie_value(original)
            result = unsign_json_cookie(signed)
            assert result == original


# =============================================================================
# Integration Tests: Jinja2 filter registration
# =============================================================================


class TestJinja2FilterRegistration:
    """Verify the sanitize filter is registered on the Jinja2 template environment."""

    def test_filter_registered_on_cached_templates(self) -> None:
        """The sanitize filter must be present in the cached templates environment."""
        from src.api.dependencies import get_cached_templates

        get_cached_templates.cache_clear()
        templates = get_cached_templates()
        assert "sanitize" in templates.env.filters

    def test_filter_registered_on_dependency_templates(self) -> None:
        """The sanitize filter must be present when using get_templates dependency."""
        from src.api.config import get_settings
        from src.api.dependencies import get_templates

        settings = get_settings()
        templates = get_templates(settings)
        assert "sanitize" in templates.env.filters

    def test_filter_returns_markup(self) -> None:
        """The sanitize filter must return a markupsafe.Markup instance."""
        from src.api.dependencies import _sanitize_filter

        result = _sanitize_filter("<p>Hello</p>")
        assert isinstance(result, markupsafe.Markup)

    def test_filter_sanitizes_and_marks_safe(self) -> None:
        """The filter must sanitize HTML and return Markup (safe) result."""
        from src.api.dependencies import _sanitize_filter

        result = _sanitize_filter('<p>Hello</p><script>alert("xss")</script>')
        assert isinstance(result, markupsafe.Markup)
        assert "<p>Hello</p>" in result
        assert "<script>" not in result

    def test_filter_in_app_templates(self) -> None:
        """The sanitize filter must be available in the running app's templates."""
        from src.api.config import get_settings
        from src.api.dependencies import get_cached_templates

        get_settings.cache_clear()
        get_cached_templates.cache_clear()

        templates = get_cached_templates()
        env = templates.env

        # Render a simple template string to verify the filter works end-to-end
        template = env.from_string("{{ content | sanitize }}")
        rendered = template.render(content="<p>OK</p><script>bad()</script>")
        assert "<p>OK</p>" in rendered
        assert "<script>" not in rendered
        assert "bad" not in rendered
