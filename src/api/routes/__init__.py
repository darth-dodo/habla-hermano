"""API routes package.

Contains all FastAPI routers for the application.
"""

from src.api.routes import (
    auth,
    chat,
    chat_stream,
    learn,
    lessons,
    privacy,
    progress,
    review,
    threads,
    voice,
)

__all__ = [
    "auth",
    "chat",
    "chat_stream",
    "learn",
    "lessons",
    "privacy",
    "progress",
    "review",
    "threads",
    "voice",
]
