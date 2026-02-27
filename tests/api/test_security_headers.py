"""Tests for SecurityHeadersMiddleware CSP nonce generation.

Validates that:
- Each response includes a CSP header with a per-request nonce.
- The nonce changes between requests (not reused).
- The nonce is stored on request.state for template access.
"""

import re

from fastapi.testclient import TestClient


class TestCSPNonce:
    """Tests for nonce-based Content Security Policy."""

    def test_csp_header_contains_nonce(self, test_client: TestClient) -> None:
        """CSP script-src should include a nonce directive."""
        response = test_client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        assert "'nonce-" in csp, f"CSP missing nonce: {csp}"

    def test_nonce_format_is_valid(self, test_client: TestClient) -> None:
        """Nonce should be a URL-safe base64 string."""
        response = test_client.get("/health")
        csp = response.headers["Content-Security-Policy"]
        # Extract nonce value from 'nonce-<value>'
        match = re.search(r"'nonce-([A-Za-z0-9_-]+)'", csp)
        assert match is not None, f"Could not extract nonce from CSP: {csp}"
        nonce = match.group(1)
        # secrets.token_urlsafe(16) produces 22-char strings
        assert len(nonce) >= 16, f"Nonce too short: {nonce}"

    def test_nonce_changes_per_request(self, test_client: TestClient) -> None:
        """Each request should generate a unique nonce."""
        nonces: set[str] = set()
        for _ in range(5):
            response = test_client.get("/health")
            csp = response.headers["Content-Security-Policy"]
            match = re.search(r"'nonce-([A-Za-z0-9_-]+)'", csp)
            assert match is not None
            nonces.add(match.group(1))
        assert len(nonces) == 5, f"Nonces should all be unique, got {len(nonces)} unique out of 5"

    def test_unsafe_inline_removed_from_script_src(self, test_client: TestClient) -> None:
        """script-src should NOT contain 'unsafe-inline' (replaced by nonce)."""
        response = test_client.get("/health")
        csp = response.headers["Content-Security-Policy"]
        # Extract just the script-src directive
        script_src_match = re.search(r"script-src\s+([^;]+)", csp)
        assert script_src_match is not None
        script_src = script_src_match.group(1)
        assert "'unsafe-inline'" not in script_src, (
            f"script-src should use nonce instead of 'unsafe-inline': {script_src}"
        )

    def test_unsafe_eval_retained_for_tailwind(self, test_client: TestClient) -> None:
        """script-src should still include 'unsafe-eval' for Tailwind CDN."""
        response = test_client.get("/health")
        csp = response.headers["Content-Security-Policy"]
        assert "'unsafe-eval'" in csp, "Tailwind CDN requires 'unsafe-eval'"

    def test_nonce_in_rendered_html(self, test_client: TestClient) -> None:
        """Rendered HTML pages should include the nonce on script tags."""
        response = test_client.get("/")
        html = response.text
        # Extract nonce from CSP header
        csp = response.headers["Content-Security-Policy"]
        match = re.search(r"'nonce-([A-Za-z0-9_-]+)'", csp)
        assert match is not None
        nonce = match.group(1)
        # The nonce should appear in the rendered HTML
        assert f'nonce="{nonce}"' in html, (
            f"Script tags in rendered HTML should include nonce=\"{nonce}\""
        )

    def test_standard_security_headers_present(self, test_client: TestClient) -> None:
        """Verify other security headers are still present."""
        response = test_client.get("/health")
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "microphone=(self)" in response.headers["Permissions-Policy"]
