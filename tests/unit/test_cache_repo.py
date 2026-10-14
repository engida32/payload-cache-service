from sqlmodel import Session

from payload_cache.db.session import create_db_engine, init_db
from payload_cache.services.cache import TransformCacheRepository


def _repo(tmp_path, version=1):
    engine = create_db_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(engine)
    return TransformCacheRepository(Session(engine), version)


def test_set_then_get(tmp_path):
    repo = _repo(tmp_path)
    repo.set_many({"a": "A", "b": "B"})
    repo.session.commit()
    assert repo.get_many(["a", "b", "missing"]) == {"a": "A", "b": "B"}


def test_get_many_empty_keys(tmp_path):
    assert _repo(tmp_path).get_many([]) == {}


def test_duplicate_insert_is_idempotent(tmp_path):
    repo = _repo(tmp_path)
    repo.set_many({"a": "A"})
    repo.session.commit()
    repo.set_many({"a": "SHOULD_NOT_WIN"})
    repo.session.commit()
    assert repo.get_many(["a"]) == {"a": "A"}


def test_version_isolated(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(engine)
    v1 = TransformCacheRepository(Session(engine), 1)
    v1.set_many({"a": "A"})
    v1.session.commit()
    assert TransformCacheRepository(Session(engine), 2).get_many(["a"]) == {}
