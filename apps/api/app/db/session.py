"""Database session and engine configuration."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache()
def get_engine() -> AsyncEngine:
    """Create and cache the async SQLAlchemy engine."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


@lru_cache()
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create and cache the async session factory."""
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for request-scoped dependencies."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
