"""FastAPI application entry point.

Creates and configures the FastAPI application with routes, static files,
and lifespan management.
"""

import logging
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from src.agent.checkpoint_purge import purge_old_checkpoints
from src.agent.checkpointer import close_checkpointer, init_checkpointer
from src.api.config import get_settings
from src.api.middleware import CSRFMiddleware, SecurityHeadersMiddleware
from src.api.dependencies import get_cached_templates
from src.api.routes import auth, chat, learn, lessons, progress, review, voice
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

# Silence noisy third-party loggers
logging.getLogger("MARKDOWN").setLevel(logging.WARNING)

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

    # Purge stale checkpoints (best-effort; failures do not block startup)
    try:
        await purge_old_checkpoints()
    except Exception:
        logger.exception("Checkpoint purge failed during startup — continuing")

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
    app.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
    app.include_router(progress.router, prefix="/progress", tags=["progress"])
    app.include_router(review.router)
    app.include_router(learn.router, prefix="/learn", tags=["learn"])
    app.include_router(voice.router)

    # --- Custom error pages ---

    def _ensure_csp_nonce(request: Request) -> None:
        """Ensure request.state.csp_nonce exists for template rendering."""
        if not hasattr(request.state, "csp_nonce"):
            request.state.csp_nonce = secrets.token_urlsafe(16)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
        # Let HTMX partial requests and API calls pass through as-is
        # so frontend JS can handle errors inline (e.g. toast, retry).
        if request.headers.get("HX-Request"):
            return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)

        _ensure_csp_nonce(request)
        templates = get_cached_templates()
        status_code = exc.status_code

        if status_code == 404:
            return templates.TemplateResponse(
                request=request,
                name="errors/404.html",
                context={},
                status_code=404,
            )

        if 400 <= status_code < 500:
            return templates.TemplateResponse(
                request=request,
                name="errors/400.html",
                context={"detail": exc.detail},
                status_code=status_code,
            )

        # 5xx errors
        return templates.TemplateResponse(
            request=request,
            name="errors/500.html",
            context={},
            status_code=status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> HTMLResponse:
        _ensure_csp_nonce(request)
        templates = get_cached_templates()
        return templates.TemplateResponse(
            request=request,
            name="errors/400.html",
            context={"detail": "Invalid request parameters."},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        _ensure_csp_nonce(request)
        templates = get_cached_templates()
        return templates.TemplateResponse(
            request=request,
            name="errors/500.html",
            context={},
            status_code=500,
        )

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
