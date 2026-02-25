"""Security headers middleware for OWASP compliance.

Adds standard security headers to every HTTP response. The HSTS header
is only included when DEBUG is False (production) because local development
typically runs over plain HTTP.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.api.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Headers applied:
    - X-Frame-Options: DENY
    - X-Content-Type-Options: nosniff
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: camera=(), microphone=(), geolocation=()
    - Content-Security-Policy: (allows HTMX, Alpine.js, Tailwind CDN)
    - Strict-Transport-Security: (production only)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and add security headers to response."""
        response = await call_next(request)

        settings = get_settings()

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # microphone=(self) needed for voice STT feature
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"

        # CSP: Allow inline scripts/styles for HTMX and Alpine.js,
        # CDN resources for Tailwind and HTMX, WebSocket for voice STT
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self' ws://localhost:* wss://localhost:*; "
            "media-src 'self' blob:"
        )

        # HSTS only in production (HTTPS)
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
