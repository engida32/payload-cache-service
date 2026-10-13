"""HTTP endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from payload_cache.api.deps import get_transformer
from payload_cache.api.schemas import (
    PayloadCreatedResponse,
    PayloadRequest,
    PayloadResponse,
)
from payload_cache.core.config import Settings, get_settings
from payload_cache.db.session import get_session
from payload_cache.services.payload import PayloadService
from payload_cache.services.transformer import Transformer

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/payload", response_model=PayloadCreatedResponse)
def create_payload(
    payload: PayloadRequest,
    session: Session = Depends(get_session),  # noqa: B008
    transformer: Transformer = Depends(get_transformer),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> PayloadCreatedResponse:
    service = PayloadService(session, version=settings.cache_version)
    pid, cached = service.create(payload.list_1, payload.list_2, transformer)
    return PayloadCreatedResponse(id=pid, cached=cached)


@router.get("/payload/{payload_id}", response_model=PayloadResponse)
def read_payload(
    payload_id: str,
    session: Session = Depends(get_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> PayloadResponse:
    service = PayloadService(session, version=settings.cache_version)
    output = service.get(payload_id)
    if output is None:
        raise HTTPException(status_code=404, detail="payload not found")
    return PayloadResponse(output=output)
