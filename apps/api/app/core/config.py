"""Application configuration."""

from functools import lru_cache

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        app_name: str = "TravelTom API"
        api_prefix: str = "/api/v1"
        environment: str = "local"

        model_config = SettingsConfigDict(env_prefix="TRAVELTOM_")

except ImportError:  # pragma: no cover - fallback for Pydantic v1
    from pydantic import BaseSettings

    class Settings(BaseSettings):
        app_name: str = "TravelTom API"
        api_prefix: str = "/api/v1"
        environment: str = "local"

        class Config:
            env_prefix = "TRAVELTOM_"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
