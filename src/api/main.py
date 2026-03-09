"""FastAPI application entry point.

Creates and configures the FastAPI application with routes, static files,
and lifespan management.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from src.agent.checkpointer import close_checkpointer, init_checkpointer
from src.api.config import get_settings
from src.api.middleware import CSRFMiddleware, SecurityHeadersMiddleware
from src.api.routes import auth, chat, learn, lesson_chat, lessons, progress, review, voice
from src.lessons.service import get_lesson_service

# Configure logging
settings = get_settings()

if settings.LOG_FORMAT == "json":
    from pythonjsonlogger.json import JsonFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    )
    logging.root.handlers = [handler]
    logging.root.setLevel(settings.log_level)
else:
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

    # Pre-warm cached singletons so the first request isn't slow
    get_settings()
    get_lesson_service()

    # Initialise persistent Postgres checkpointer (connection pool + DDL once)
    await init_checkpointer()

    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)
    await close_checkpointer()


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

    # Security middleware (applied in reverse order — last added runs first)
    # 1. SecurityHeaders runs last (outermost): adds security headers to responses
    # 2. CSRF runs before route handlers: rejects forged state-changing requests
    # 3. CORS runs first (innermost): handles preflight OPTIONS and origin checks
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://localhost:{settings.PORT}", f"http://127.0.0.1:{settings.PORT}"]
        if settings.DEBUG
        else [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
        or [f"https://{settings.HOST}"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
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
    app.include_router(lesson_chat.router)
    app.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
    app.include_router(progress.router, prefix="/progress", tags=["progress"])
    app.include_router(review.router)
    app.include_router(learn.router, prefix="/learn", tags=["learn"])
    app.include_router(voice.router)
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
