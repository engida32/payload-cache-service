"""Level-1 cache and orchestration: idempotent payload creation.

Order matters — the transformer (a slow external call) runs *outside* the DB
write, so no lock is held across the network hop. Concurrent requests for the
same payload are collapsed into one build by a single-flight gate keyed on the
payload id.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from payload_cache.core.hashing import canonical_payload, payload_id
from payload_cache.db.models import Payload
from payload_cache.services.cache import TransformCacheRepository
from payload_cache.services.singleflight import SingleFlight
from payload_cache.services.transformer import Transformer

_flights = SingleFlight()


class PayloadCollisionError(RuntimeError):
    """A stored payload has the same id but different input (sha256 collision)."""


class PayloadService:
    def __init__(self, session: Session, version: int) -> None:
        self.session = session
        self.version = version

    def create(
        self, list_1: list[str], list_2: list[str], transformer: Transformer
    ) -> tuple[str, bool]:
        if len(list_1) != len(list_2):
            raise ValueError("list_1 and list_2 must have the same length")

        canonical = canonical_payload(list_1, list_2, self.version)
        pid = payload_id(list_1, list_2, self.version)

        existing = self.session.get(Payload, pid)
        if existing is not None:
            if existing.input_json != canonical:
                raise PayloadCollisionError(pid)
            return existing.id, True

        stored, leader = _flights.run(
            pid, lambda: self._store(pid, canonical, list_1, list_2, transformer)
        )
        if not leader:
            # This session read the table before the leader committed.
            self.session.rollback()
        return pid, not (stored and leader)

    def _store(
        self,
        pid: str,
        canonical: str,
        list_1: list[str],
        list_2: list[str],
        transformer: Transformer,
    ) -> bool:
        existing = self.session.get(Payload, pid)
        if existing is not None:
            if existing.input_json != canonical:
                raise PayloadCollisionError(pid)
            return True

        output = self._build(list_1, list_2, transformer)

        row = Payload(id=pid, input_json=canonical, output=output)
        try:
            with self.session.begin_nested():
                self.session.add(row)
            self.session.commit()
        except IntegrityError:
            # A concurrent request created the same payload first.
            self.session.rollback()
            return False
        return True

    def get(self, pid: str) -> str | None:
        row = self.session.get(Payload, pid)
        return row.output if row is not None else None

    def _build(self, list_1: list[str], list_2: list[str], transformer: Transformer) -> str:
        cache = TransformCacheRepository(self.session, self.version)
        distinct = list(dict.fromkeys([*list_1, *list_2]))
        cached = cache.get_many(distinct)
        missing = [value for value in distinct if value not in cached]
        if missing:
            new_values = dict(zip(missing, transformer.transform_batch(missing), strict=False))
            cache.set_many(new_values)
            self.session.commit()
            cached.update(new_values)
        t1 = [cached[value] for value in list_1]
        t2 = [cached[value] for value in list_2]
        return ", ".join(token for pair in zip(t1, t2, strict=False) for token in pair)
