"""Application configuration using Pydantic Settings.

Loads configuration from environment variables with .env file support.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        ANTHROPIC_API_KEY: API key for Anthropic Claude models.
        DEBUG: Enable debug mode with detailed errors and auto-reload.
        APP_NAME: Display name for the application.
        LLM_MODEL: Claude model identifier to use.
        LLM_TEMPERATURE: Sampling temperature for LLM responses.
        HOST: Server host address.
        PORT: Server port number.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Required settings
    ANTHROPIC_API_KEY: str

    # Application settings
    APP_NAME: str = "Habla Hermano"
    DEBUG: bool = False

    # LLM settings
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_TEMPERATURE: float = 0.7

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Paths (computed relative to project root)
    @property
    def project_root(self) -> Path:
        """Return the project root directory."""
        return Path(__file__).parent.parent.parent

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


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance.

    Uses lru_cache to ensure settings are only loaded once.

    Returns:
        Settings: Application settings instance.
    """
    return Settings()  # type: ignore[call-arg]
