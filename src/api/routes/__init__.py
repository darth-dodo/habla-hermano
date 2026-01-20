"""API routes package.

Contains all FastAPI routers for the application.
"""

from src.api.routes import auth, chat

__all__ = ["auth", "chat"]
