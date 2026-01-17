"""FastAPI dependency injection providers.

Provides reusable dependencies for routes including settings and templates.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.templating import Jinja2Templates

from src.api.config import Settings, get_settings


def get_templates(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Jinja2Templates:
    """Return Jinja2Templates instance configured with templates directory.

    Args:
        settings: Application settings instance.

    Returns:
        Jinja2Templates: Configured template engine.
    """
    return Jinja2Templates(directory=str(settings.templates_dir))


@lru_cache
def get_cached_templates() -> Jinja2Templates:
    """Return cached Jinja2Templates instance.

    Uses lru_cache to avoid recreating templates engine on every request.
    Use this for performance-critical paths.

    Returns:
        Jinja2Templates: Cached template engine instance.
    """
    settings = get_settings()
    return Jinja2Templates(directory=str(settings.templates_dir))


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_cached_templates)]
