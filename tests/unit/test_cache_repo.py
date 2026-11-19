from datetime import timedelta

from sqlmodel import Session, select

from payload_cache.db.models import TransformCache, utcnow
from payload_cache.db.session import create_db_engine, init_db
from payload_cache.services.cache import TransformCacheRepository


def _repo(tmp_path, version=1, ttl_seconds=0):
    engine = create_db_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(engine)
    return TransformCacheRepository(Session(engine), version, ttl_seconds)


def test_set_then_get(tmp_path):
    repo = _repo(tmp_path)
    repo.set_many({"a": "A", "b": "B"})
    repo.session.commit()
    assert repo.get_many(["a", "b", "missing"]) == {"a": "A", "b": "B"}


def test_get_many_empty_keys(tmp_path):
    assert _repo(tmp_path).get_many([]) == {}


def test_rewrite_refreshes_the_stored_value(tmp_path):
    repo = _repo(tmp_path)
    repo.set_many({"a": "A"})
    repo.session.commit()
    repo.set_many({"a": "B"})
    repo.session.commit()
    assert repo.get_many(["a"]) == {"a": "B"}


def test_version_isolated(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(engine)
    v1 = TransformCacheRepository(Session(engine), 1)
    v1.set_many({"a": "A"})
    v1.session.commit()
    assert TransformCacheRepository(Session(engine), 2).get_many(["a"]) == {}


def test_rows_older_than_the_ttl_are_ignored(tmp_path):
    repo = _repo(tmp_path, ttl_seconds=60)
    repo.set_many({"a": "A"})
    row = repo.session.exec(select(TransformCache)).first()
    row.created_at = utcnow() - timedelta(seconds=61)
    repo.session.add(row)
    repo.session.commit()
    assert repo.get_many(["a"]) == {}


def test_expired_key_can_be_stored_again(tmp_path):
    repo = _repo(tmp_path, ttl_seconds=60)
    repo.set_many({"a": "A"})
    row = repo.session.exec(select(TransformCache)).first()
    row.created_at = utcnow() - timedelta(seconds=61)
    repo.session.add(row)
    repo.session.commit()

    repo.set_many({"a": "B"})
    repo.session.commit()
    assert repo.get_many(["a"]) == {"a": "B"}
