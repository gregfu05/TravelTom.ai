"""Application configuration."""

from functools import lru_cache

try:
    from pydantic import AliasChoices, Field
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        app_name: str = "TravelTom API"
        api_prefix: str = "/api/v1"
        environment: str = Field("local", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"))
        database_url: str = Field(..., validation_alias="DATABASE_URL")

        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

except ImportError:  # pragma: no cover - fallback for Pydantic v1
    from pydantic import BaseSettings, Field

    class Settings(BaseSettings):
        app_name: str = "TravelTom API"
        api_prefix: str = "/api/v1"
        environment: str = Field("local", env=["APP_ENV", "ENVIRONMENT"])
        database_url: str = Field(..., env="DATABASE_URL")

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
