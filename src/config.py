"""Application configuration using Pydantic Settings.

Loads configuration from environment variables with .env file support.
This module lives at the ``src`` level so that inner layers (agent, services, db)
can import it without depending on the API layer.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        OPENROUTER_API_KEY: API key for OpenRouter (routes to Claude and other models).
        OPENROUTER_BASE_URL: Base URL for the OpenRouter OpenAI-compatible API.
        DEBUG: Enable debug mode with detailed errors and auto-reload.
        APP_NAME: Display name for the application.
        LLM_MODEL: OpenRouter model identifier to use (e.g. "anthropic/claude-haiku-4.5").
        LLM_TEMPERATURE: Sampling temperature for LLM responses.
        HOST: Server host address.
        PORT: Server port number.
        SECRET_KEY: Secret key for signing cookies and other tokens.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Required settings
    OPENROUTER_API_KEY: str

    # Supabase settings (required for auth and persistence)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_DB_URL: str = ""
    # Optional: Service key for admin operations (bypasses RLS)
    SUPABASE_SERVICE_KEY: str = ""

    # Application settings
    APP_NAME: str = "Habla Hermano"
    DEBUG: bool = False

    # Security: allow unverified JWT decode when Supabase is not configured.
    # WARNING: NEVER set to true in production. Only for local development.
    ALLOW_UNVERIFIED_JWT: bool = False

    # Secret key for signing cookies (review sessions, etc.)
    SECRET_KEY: str = "change-me-to-a-random-string"

    # Salt for deriving the encryption key from SECRET_KEY (PBKDF2)
    ENCRYPTION_SALT: str = ""

    # Voice features (Phase 17) - Deepgram STT/TTS
    DEEPGRAM_API_KEY: str = ""

    # LLM settings (via OpenRouter, OpenAI-compatible API)
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "anthropic/claude-haiku-4.5"
    LLM_TEMPERATURE: float = 0.7

    # Optional OpenRouter app attribution (sent as HTTP-Referer / X-Title headers).
    # Used for OpenRouter's per-app usage rankings; safe to leave empty.
    OPENROUTER_APP_URL: str = ""
    OPENROUTER_APP_TITLE: str = ""

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # CORS: comma-separated origins for production (e.g. "https://habla-hermano.onrender.com")
    # Leave empty for same-origin (server-rendered apps typically don't need cross-origin)
    CORS_ALLOWED_ORIGINS: str = ""

    # Logging format: "text" for human-readable, "json" for structured logging
    LOG_FORMAT: Literal["text", "json"] = "text"

    # Sentry error monitoring (empty DSN = disabled)
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_ENVIRONMENT: str = ""

    # Privacy: when true, restrict OpenRouter routing to providers that do not
    # collect/train on data (sends provider.data_collection="deny" in requests).
    OPENROUTER_ZERO_RETENTION: bool = False

    # Auto-delete conversation data older than N days (0 = disabled)
    CONVERSATION_RETENTION_DAYS: int = 0

    # Checkpoint retention: auto-purge checkpoints older than this many days (0 = disabled)
    CHECKPOINT_RETENTION_DAYS: int = 30

    # Paths (computed relative to project root)
    _INSECURE_SECRET_KEY: str = "change-me-to-a-random-string"
    _INSECURE_SALT: str = "habla-hermano-encryption-v1"

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Self:
        """Reject insecure defaults when running in production (DEBUG=False)."""
        if not self.DEBUG:
            if self.SECRET_KEY == self._INSECURE_SECRET_KEY:
                raise ValueError(
                    "SECRET_KEY must be set to a strong random value in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
                )
            if (
                self.ENCRYPTION_SALT == self._INSECURE_SALT
                and self.SECRET_KEY == self._INSECURE_SECRET_KEY
            ):
                raise ValueError(
                    "ENCRYPTION_SALT must be set to a unique value in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
                )
            if self.ALLOW_UNVERIFIED_JWT:
                raise ValueError(
                    "ALLOW_UNVERIFIED_JWT=true is forbidden in production (DEBUG=False). "
                    "This bypasses JWT signature verification."
                )
        return self

    @property
    def project_root(self) -> Path:
        """Return the project root directory."""
        return Path(__file__).parent.parent

    @property
    def templates_dir(self) -> Path:
        """Return the templates directory path."""
        return self.project_root / "src" / "templates"

    @property
    def static_dir(self) -> Path:
        """Return the static files directory path."""
        return self.project_root / "src" / "static"

    @property
    def log_level(self) -> Literal["DEBUG", "INFO", "WARNING", "ERROR"]:
        """Return appropriate log level based on DEBUG setting."""
        return "DEBUG" if self.DEBUG else "INFO"

    @property
    def supabase_configured(self) -> bool:
        """Check if Supabase Auth is configured.

        Returns:
            True if URL and anon key are provided (for auth).
            Note: DB_URL is optional - only needed for Postgres checkpointing.
        """
        return bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY)

    @property
    def voice_enabled(self) -> bool:
        """Check if voice features are configured."""
        return bool(self.DEEPGRAM_API_KEY)


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance.

    Uses lru_cache to ensure settings are only loaded once.

    Returns:
        Settings: Application settings instance.
    """
    return Settings()  # type: ignore[call-arg]  # pydantic-settings populates fields from env
