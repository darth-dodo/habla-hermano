"""API routes package.

Contains all FastAPI routers for the application.
"""

from src.api.routes import auth, chat, voice

__all__ = ["auth", "chat", "voice"]
