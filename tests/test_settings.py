"""Tests for configuration loading behavior."""

from app.core.config import get_settings


def test_settings_use_environment_aliases(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://traveltom:traveltom@localhost:5432/test_db",
    )
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_TENANT_NAME", "traveltomtest")
    monkeypatch.setenv("AUTH_POLICY_NAME", "B2C_1_signin")
    monkeypatch.setenv("AUTH_APP_CLIENT_ID", "client-id")
    monkeypatch.setenv("AUTH_REQUIRED_SCOPES", "user_impersonation api.read")
    monkeypatch.setenv("LOCAL_AUTH_TOKEN_SECRET", "local-secret")
    monkeypatch.setenv("LOCAL_AUTH_TOKEN_TTL_SECONDS", "7200")

    settings = get_settings()

    assert settings.environment == "test"
    assert settings.database_url.endswith("/test_db")
    assert settings.auth_enabled is True
    assert settings.auth_required_scopes_list == ["user_impersonation", "api.read"]
    assert settings.auth_openid_config_url is not None
    assert settings.local_auth_enabled is True
    assert settings.local_auth_token_ttl_seconds == 7200
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
