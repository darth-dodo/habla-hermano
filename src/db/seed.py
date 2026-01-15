"""Seed data for initial database population."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Base, async_session_factory, engine, init_db
from src.db.repository import SettingsRepository

# Default settings for MVP
DEFAULT_SETTINGS: dict[str, str] = {
    "current_language": "es",
    "current_level": "A0",
    "scaffolding_enabled": "true",
    "auto_translate": "true",
}


async def seed_settings(session: AsyncSession) -> None:
    """Seed default settings if not present."""
    repo = SettingsRepository(session)
    for key, value in DEFAULT_SETTINGS.items():
        existing = await repo.get(key)
        if existing is None:
            await repo.set(key, value)


async def seed_database() -> None:
    """Initialize and seed the database with default data."""
    await init_db()

    async with async_session_factory() as session:
        await seed_settings(session)


async def reset_database() -> None:
    """Reset database to initial state (for development)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await seed_database()


__all__ = ["DEFAULT_SETTINGS", "reset_database", "seed_database", "seed_settings"]
