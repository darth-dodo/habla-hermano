"""Security middleware for OWASP compliance.

Provides two middleware classes:
- SecurityHeadersMiddleware: Adds standard security headers to every HTTP response,
  including Cache-Control for static assets.
- CSRFMiddleware: Protects state-changing requests (POST/PUT/DELETE/PATCH) using
  the "custom header" CSRF pattern.

The HSTS header is only included when DEBUG is False (production) because local
development typically runs over plain HTTP.
"""

import logging
import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.api.config import get_settings

logger = logging.getLogger(__name__)

# HTTP methods that change state and require CSRF protection
_STATE_CHANGING_METHODS: frozenset[str] = frozenset({"POST", "PUT", "DELETE", "PATCH"})

# Paths exempt from CSRF checks (health checks, static assets)
_CSRF_EXEMPT_PATHS: frozenset[str] = frozenset({"/health"})

# Path prefixes exempt from CSRF (static files served by StaticFiles mount)
_CSRF_EXEMPT_PREFIXES: tuple[str, ...] = ("/static/",)

# Cache-Control settings for static assets.
# In DEBUG mode, use a short max-age (1 hour) to ease local development.
# In production, cache for 1 day and allow shared caches to store assets.
_STATIC_CACHE_DEBUG: str = "public, max-age=3600"
_STATIC_CACHE_PRODUCTION: str = "public, max-age=86400"

# Static asset path prefix
_STATIC_PREFIX: str = "/static/"


def _is_csrf_exempt(method: str, path: str) -> bool:
    """Check whether a request is exempt from CSRF validation.

    A request is exempt if:
    - Its HTTP method is safe (not in _STATE_CHANGING_METHODS or is OPTIONS)
    - Its path matches an exact exempt path or an exempt prefix

    Args:
        method: Uppercased HTTP method (e.g. "POST").
        path: Request URL path (e.g. "/chat").

    Returns:
        True if the request should skip CSRF validation.
    """
    if method not in _STATE_CHANGING_METHODS:
        return True
    if path in _CSRF_EXEMPT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _CSRF_EXEMPT_PREFIXES)


def _has_csrf_header(request: Request) -> bool:
    """Check whether the request carries a valid CSRF-proving header.

    Accepts:
    - ``HX-Request: true`` (HTMX automatic header)
    - ``X-Requested-With: XMLHttpRequest`` (conventional XHR/fetch marker)

    Args:
        request: Incoming HTTP request.

    Returns:
        True if a valid CSRF header is present.
    """
    hx_request = request.headers.get("hx-request", "").lower()
    if hx_request == "true":
        return True

    x_requested_with = request.headers.get("x-requested-with", "").lower()
    return x_requested_with == "xmlhttprequest"


class CSRFMiddleware(BaseHTTPMiddleware):
    """Protect state-changing endpoints against Cross-Site Request Forgery.

    Uses the "custom header" pattern recommended by OWASP:
    https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

    For HTMX requests:
        HTMX automatically sends ``HX-Request: true`` on every request it makes.
        Browsers will not send custom headers cross-origin without a CORS preflight,
        so the presence of this header proves the request is same-origin.

    For JavaScript fetch() requests (stream.js, voice.js):
        These include ``X-Requested-With: XMLHttpRequest`` which similarly cannot
        be forged cross-origin without CORS approval.

    Exempt from CSRF:
        - GET, HEAD, OPTIONS requests (safe methods)
        - ``/health`` endpoint
        - Static file paths (``/static/``)
        - WebSocket upgrade requests (handled by a different protocol)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Check CSRF headers on state-changing requests."""
        method = request.method.upper()
        path = request.url.path

        # Skip CSRF for safe methods and exempt paths
        if _is_csrf_exempt(method, path):
            return await call_next(request)

        # Validate that a CSRF-proving header is present
        if _has_csrf_header(request):
            return await call_next(request)

        # None of the CSRF signals matched -- reject the request
        logger.warning(
            "CSRF validation failed: %s %s (missing HX-Request or X-Requested-With header)",
            method,
            path,
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF validation failed"},
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Headers applied:
    - X-Frame-Options: DENY
    - X-Content-Type-Options: nosniff
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: camera=(), microphone=(self), geolocation=()
    - Content-Security-Policy: (allows HTMX, Alpine.js, Tailwind CDN)
    - Strict-Transport-Security: (production only)
    - Cache-Control: public caching for /static/ assets (duration varies by DEBUG)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and add security headers to response.

        Generates a per-request CSP nonce and stores it on ``request.state``
        so that Jinja2 templates can render ``nonce="{{ request.state.csp_nonce }}"``
        on ``<script>`` tags.  The nonce is generated **before** ``call_next()``
        to ensure it is available during template rendering.
        """
        # Generate a per-request nonce for CSP script-src
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        settings = get_settings()

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # microphone=(self) needed for voice STT feature
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"

        # CSP: Nonce-based script allowlisting with CDN origins.
        # 'unsafe-eval' remains required because Tailwind CDN uses eval() internally;
        # full removal requires a build-time CSS migration (deferred).
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "media-src 'self' blob: data:; "
            "connect-src 'self' ws: wss:"
        )

        # HSTS only in production (HTTPS)
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Cache-Control for static assets (JS, CSS, images).
        # Non-static responses intentionally omit Cache-Control so that
        # browsers follow default heuristic caching for HTML pages.
        if request.url.path.startswith(_STATIC_PREFIX):
            response.headers["Cache-Control"] = (
                _STATIC_CACHE_DEBUG if settings.DEBUG else _STATIC_CACHE_PRODUCTION
            )

        return response
