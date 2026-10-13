"""FastAPI dependencies. The transformer factory reads settings so latency is
environment-driven; tests override it with a spy."""

from fastapi import Depends

from payload_cache.core.config import Settings, get_settings
from payload_cache.services.transformer import Transformer, UppercaseTransformer


def get_transformer(settings: Settings = Depends(get_settings)) -> Transformer:  # noqa: B008
    return UppercaseTransformer(latency_ms=settings.transformer_latency_ms)
