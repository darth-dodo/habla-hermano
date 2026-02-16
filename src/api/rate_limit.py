"""Rate limiting configuration for API endpoints.

Uses slowapi to provide in-memory IP-based rate limiting.
Protects against brute force login attempts and API budget abuse.
"""

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

AUTH_RATE_LIMIT = "5/minute"
CHAT_RATE_LIMIT = "20/minute"
GENERAL_RATE_LIMIT = "60/minute"

limiter = Limiter(key_func=get_remote_address)
