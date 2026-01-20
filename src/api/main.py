"""FastAPI application entry point.

Creates and configures the FastAPI application with routes, static files,
and lifespan management.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.config import get_settings
from src.api.routes import auth, chat

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events.

    Args:
        _app: FastAPI application instance (unused, required by lifespan protocol).

    Yields:
        None: Control returns to the application during its lifetime.
    """
    # Startup
    logger.info("Starting %s...", settings.APP_NAME)
    logger.info("Debug mode: %s", settings.DEBUG)
    logger.info("Templates directory: %s", settings.templates_dir)
    logger.info("Static files directory: %s", settings.static_dir)

    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI-powered language tutor for Spanish learners",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # Mount static files
    if settings.static_dir.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(settings.static_dir)),
            name="static",
        )
        logger.info("Static files mounted at /static")
    else:
        logger.warning("Static directory not found: %s", settings.static_dir)

    # Include routers
    app.include_router(auth.router)
    app.include_router(chat.router)

    return app


# Create the application instance
app = create_app()


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        dict: Health status response.
    """
    return {"status": "healthy", "app": settings.APP_NAME}
