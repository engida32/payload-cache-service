"""Persistent tables: the payload cache (level 1) and the transform cache (level 2)."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class TransformCache(SQLModel, table=True):
    __tablename__ = "transform_cache"

    version: int = Field(primary_key=True)
    key: str = Field(primary_key=True)
    value: str
    created_at: datetime = Field(default_factory=utcnow)


class Payload(SQLModel, table=True):
    __tablename__ = "payload"

    id: str = Field(primary_key=True)
    input_json: str
    output: str
    created_at: datetime = Field(default_factory=utcnow)
