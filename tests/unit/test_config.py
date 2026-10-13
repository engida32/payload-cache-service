from payload_cache.core.config import Settings


def test_defaults():
    settings = Settings()
    assert settings.database_url == "sqlite:///./payload_cache.db"
    assert settings.transformer_latency_ms == 50
    assert settings.cache_version == 1


def test_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./other.db")
    monkeypatch.setenv("TRANSFORMER_LATENCY_MS", "0")
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:///./other.db"
    assert settings.transformer_latency_ms == 0
