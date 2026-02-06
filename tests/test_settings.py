"""Tests for configuration loading behavior."""

from app.core.config import get_settings


def test_settings_use_environment_aliases(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://traveltom:traveltom@localhost:5432/test_db",
    )
    monkeypatch.setenv("APP_ENV", "test")

    settings = get_settings()

    assert settings.environment == "test"
    assert settings.database_url.endswith("/test_db")
    get_settings.cache_clear()


def test_settings_are_cached(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://traveltom:traveltom@localhost:5432/cache_db",
    )
    monkeypatch.setenv("APP_ENV", "test")

    first = get_settings()
    second = get_settings()

    assert first is second
    get_settings.cache_clear()
