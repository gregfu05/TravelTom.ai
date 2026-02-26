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


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
