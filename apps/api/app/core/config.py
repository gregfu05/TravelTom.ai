"""Application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TravelTom API"
    api_prefix: str = "/api/v1"
    environment: str = Field(
        "local", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT")
    )
    database_url: str = Field(..., validation_alias="DATABASE_URL")
    auth_enabled: bool = Field(
        False,
        validation_alias=AliasChoices("AUTH_ENABLED"),
    )
    auth_app_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_APP_CLIENT_ID"),
    )
    auth_tenant_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_TENANT_NAME"),
    )
    auth_policy_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AUTH_POLICY_NAME"),
    )
    auth_required_scopes: str = Field(
        "user_impersonation",
        validation_alias=AliasChoices("AUTH_REQUIRED_SCOPES"),
    )
    local_auth_token_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOCAL_AUTH_TOKEN_SECRET"),
    )
    local_auth_token_ttl_seconds: int = Field(
        60 * 60 * 24 * 7,
        ge=300,
        validation_alias=AliasChoices("LOCAL_AUTH_TOKEN_TTL_SECONDS"),
    )
    local_auth_token_idle_timeout_seconds: int = Field(
        60 * 60 * 12,
        ge=300,
        validation_alias=AliasChoices("LOCAL_AUTH_TOKEN_IDLE_TIMEOUT_SECONDS"),
    )
    chat_rate_limit: str = Field(
        "30/minute",
        validation_alias=AliasChoices("CHAT_RATE_LIMIT"),
    )
    orchestrator_llm_provider: Literal["disabled", "ollama", "openai"] = Field(
        "disabled",
        validation_alias=AliasChoices("ORCHESTRATOR_LLM_PROVIDER"),
    )
    orchestrator_llm_timeout_seconds: float = Field(
        20.0,
        ge=1.0,
        validation_alias=AliasChoices("ORCHESTRATOR_LLM_TIMEOUT_SECONDS"),
    )
    ollama_base_url: str = Field(
        "http://127.0.0.1:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL"),
    )
    ollama_planning_model: str = Field(
        "llama3.1:8b",
        validation_alias=AliasChoices("OLLAMA_PLANNING_MODEL"),
    )
    ollama_response_model: str = Field(
        "llama3.1:8b",
        validation_alias=AliasChoices("OLLAMA_RESPONSE_MODEL"),
    )
    ollama_temperature: float = Field(
        0.0,
        ge=0.0,
        le=2.0,
        validation_alias=AliasChoices("OLLAMA_TEMPERATURE"),
    )
    openai_base_url: str = Field(
        "https://api.openai.com/v1",
        validation_alias=AliasChoices(
            "ORCHESTRATOR_OPENAI_BASE_URL",
            "OPENAI_BASE_URL",
        ),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ORCHESTRATOR_OPENAI_API_KEY",
            "OPENAI_API_KEY",
        ),
    )
    openai_planning_model: str = Field(
        "gpt-4.1-mini",
        validation_alias=AliasChoices("OPENAI_PLANNING_MODEL"),
    )
    openai_response_model: str = Field(
        "gpt-4.1-mini",
        validation_alias=AliasChoices("OPENAI_RESPONSE_MODEL"),
    )
    openai_temperature: float = Field(
        0.0,
        ge=0.0,
        le=2.0,
        validation_alias=AliasChoices("OPENAI_TEMPERATURE"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def auth_required_scopes_list(self) -> list[str]:
        raw_scopes = self.auth_required_scopes.replace(",", " ").split()
        return [scope for scope in raw_scopes if scope]

    @property
    def auth_openid_config_url(self) -> str | None:
        if not self.auth_tenant_name or not self.auth_policy_name:
            return None
        tenant = self.auth_tenant_name
        policy = self.auth_policy_name
        return (
            f"https://{tenant}.b2clogin.com/"
            f"{tenant}.onmicrosoft.com/"
            f"{policy}/v2.0/.well-known/openid-configuration"
        )

    @property
    def local_auth_enabled(self) -> bool:
        secret = (self.local_auth_token_secret or "").strip()
        return bool(secret)


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
