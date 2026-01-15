"""Application configuration using Pydantic Settings.

Provides typed configuration with environment variable loading and validation.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "HablaAI"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "production", "test"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    database_url: str = "sqlite+aiosqlite:///data/habla.db"
    templates_dir: Path = Field(default=None)  # type: ignore[assignment]
    static_dir: Path = Field(default=None)  # type: ignore[assignment]

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8000"])
    cors_allow_credentials: bool = True

    # Session
    secret_key: str = "change-me-in-production"
    session_cookie_name: str = "habla_session"

    def model_post_init(self, __context: object) -> None:
        """Set computed paths after initialization."""
        if self.templates_dir is None:
            object.__setattr__(self, "templates_dir", self.base_dir / "src" / "templates")
        if self.static_dir is None:
            object.__setattr__(self, "static_dir", self.base_dir / "src" / "static")


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings singleton."""
    return Settings()
