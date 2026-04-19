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
    monkeypatch.setenv("LOCAL_AUTH_TOKEN_IDLE_TIMEOUT_SECONDS", "1800")

    settings = get_settings()

    assert settings.environment == "test"
    assert settings.database_url.endswith("/test_db")
    assert settings.auth_enabled is True
    assert settings.auth_required_scopes_list == ["user_impersonation", "api.read"]
    assert settings.auth_openid_config_url is not None
    assert settings.local_auth_enabled is True
    assert settings.local_auth_token_ttl_seconds == 7200
    assert settings.local_auth_token_idle_timeout_seconds == 1800
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


def test_settings_default_to_phi35mini_for_local_chat(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://traveltom:traveltom@localhost:5432/default_db",
    )
    monkeypatch.delenv("ORCHESTRATOR_LLM_PROVIDER", raising=False)

    settings = get_settings()

    assert settings.orchestrator_llm_provider == "phi35mini"
    get_settings.cache_clear()


def test_settings_read_ml_ranker_runtime_overrides(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://traveltom:traveltom@localhost:5432/mlops_db",
    )
    monkeypatch.setenv(
        "TRAVELTOM_ML_RANKER_ARTIFACT_URI",
        "https://example.blob.core.windows.net/ml-artifacts/ranker.pkl",
    )
    monkeypatch.setenv("TRAVELTOM_ML_RANKER_PROMOTED_VERSION", "ranker-v3-dev")
    monkeypatch.setenv("TRAVELTOM_ML_RANKER_CACHE_DIR", "/tmp/traveltom-ml-cache")

    settings = get_settings()

    assert (
        settings.traveltom_ml_ranker_artifact_uri
        == "https://example.blob.core.windows.net/ml-artifacts/ranker.pkl"
    )
    assert settings.traveltom_ml_ranker_promoted_version == "ranker-v3-dev"
    assert settings.traveltom_ml_ranker_cache_dir == "/tmp/traveltom-ml-cache"
    get_settings.cache_clear()


def test_settings_accept_phi35mini_provider_and_env(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://traveltom:traveltom@localhost:5432/phi_db",
    )
    monkeypatch.setenv("ORCHESTRATOR_LLM_PROVIDER", "phi35mini")
    monkeypatch.setenv("PHI35MINI_BASE_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("PHI35MINI_PLANNING_MODEL", "phi3.5:mini-instruct")
    monkeypatch.setenv("PHI35MINI_RESPONSE_MODEL", "phi3.5:mini-instruct")
    monkeypatch.setenv("PHI35MINI_TEMPERATURE", "0.2")

    settings = get_settings()

    assert settings.orchestrator_llm_provider == "phi35mini"
    assert settings.phi35mini_base_url == "http://127.0.0.1:11435"
    assert settings.phi35mini_planning_model == "phi3.5:mini-instruct"
    assert settings.phi35mini_response_model == "phi3.5:mini-instruct"
    assert settings.phi35mini_temperature == 0.2
    get_settings.cache_clear()
