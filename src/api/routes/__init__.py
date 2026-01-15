"""API route modules for HablaAI.

Contains chat, lessons, and progress endpoints with HTMX response patterns.
"""

from src.api.routes import chat, lessons, progress

__all__ = ["chat", "lessons", "progress"]
