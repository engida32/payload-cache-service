"""Level-2 cache: memoized transformer output per (version, raw string).

Writes are race-safe with a portable mechanism: the insert runs inside a
SAVEPOINT, so a duplicate-key IntegrityError (two requests transforming the same
new string at once) rolls back only that row and the transaction survives.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from payload_cache.db.models import TransformCache


class TransformCacheRepository:
    def __init__(self, session: Session, version: int) -> None:
        self.session = session
        self.version = version

    def get_many(self, keys: list[str]) -> dict[str, str]:
        if not keys:
            return {}
        statement = select(TransformCache).where(
            TransformCache.version == self.version,
            col(TransformCache.key).in_(keys),
        )
        return {row.key: row.value for row in self.session.exec(statement)}

    def set_many(self, items: dict[str, str]) -> None:
        for key, value in items.items():
            row = TransformCache(version=self.version, key=key, value=value)
            try:
                with self.session.begin_nested():
                    self.session.add(row)
            except IntegrityError:
                continue
