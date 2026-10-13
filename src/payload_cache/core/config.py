"""Application settings.

Env vars are unprefixed (DATABASE_URL, TRANSFORMER_LATENCY_MS, CACHE_VERSION)
so the service drops cleanly into container/platform configuration.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./payload_cache.db"
    transformer_latency_ms: int = 50
    cache_version: int = 1


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the app reads the environment once."""
    return Settings()
