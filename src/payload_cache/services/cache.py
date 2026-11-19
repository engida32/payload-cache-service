"""Level-2 cache: memoized transformer output per (version, raw string).

Writes are race-safe with a portable mechanism: the insert runs inside a
SAVEPOINT, so a duplicate-key IntegrityError (two requests transforming the same
new string at once) rolls back only that row and the transaction survives.

A positive TTL turns reads into a window: older rows are ignored, and a write
refreshes the row instead of colliding with it, so an expired key can be stored
again.
"""

from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from payload_cache.db.models import TransformCache, utcnow


class TransformCacheRepository:
    def __init__(self, session: Session, version: int, ttl_seconds: int = 0) -> None:
        self.session = session
        self.version = version
        self.ttl_seconds = ttl_seconds

    def get_many(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        statement = select(TransformCache).where(
            TransformCache.version == self.version,
            col(TransformCache.key).in_(keys),
        )
        if self.ttl_seconds > 0:
            statement = statement.where(
                col(TransformCache.created_at) >= utcnow() - timedelta(seconds=self.ttl_seconds)
            )
        return {row.key: row.value for row in self.session.exec(statement)}

    def set_many(self, items: dict[str, str]) -> None:
        if not items:
            return
        now = utcnow()
        existing = {
            row.key: row
            for row in self.session.exec(
                select(TransformCache).where(
                    TransformCache.version == self.version,
                    col(TransformCache.key).in_(list(items)),
                )
            )
        }
        for key, value in items.items():
            row = existing.get(key)
            if row is not None:
                row.value = value
                row.created_at = now
                self.session.add(row)
                continue
            try:
                with self.session.begin_nested():
                    self.session.add(
                        TransformCache(version=self.version, key=key, value=value, created_at=now)
                    )
            except IntegrityError:
                continue
