"""FastAPI application factory and configuration.

Entry point for the HablaAI web application with HTMX support.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.config import get_settings
from src.api.routes import chat, lessons, progress


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager for startup and shutdown events.

    Args:
        _app: FastAPI application instance (unused in stub).

    Yields:
        None: Control returns to application during runtime.
    """
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application with routes, middleware, and static files.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    if settings.static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    # Route registration
    app.include_router(chat.router, prefix="/chat", tags=["chat"])
    app.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
    app.include_router(progress.router, prefix="/progress", tags=["progress"])

    return app


# Application instance for uvicorn
app = create_app()
