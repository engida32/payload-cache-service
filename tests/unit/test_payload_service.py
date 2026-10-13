import pytest
from sqlmodel import Session

from payload_cache.core import hashing
from payload_cache.db.session import create_db_engine, init_db
from payload_cache.services.payload import PayloadCollisionError, PayloadService


class SpyTransformer:
    def __init__(self):
        self.calls: list[str] = []

    def transform(self, value: str) -> str:
        self.calls.append(value)
        return value.upper()

    def transform_batch(self, values: list[str]) -> list[str]:
        return [self.transform(v) for v in values]


def _service(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(engine)
    return PayloadService(Session(engine), version=1)


def test_generates_interleaved_output(tmp_path):
    service, spy = _service(tmp_path), SpyTransformer()
    pid, cached = service.create(
        ["first string", "second string", "third string"],
        ["other string", "another string", "last string"],
        spy,
    )
    assert cached is False
    assert service.get(pid) == (
        "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
    )


def test_same_input_reuses_id_and_skips_transformer(tmp_path):
    service, spy = _service(tmp_path), SpyTransformer()
    first, _ = service.create(["a"], ["b"], spy)
    calls_after_first = list(spy.calls)
    second, cached = service.create(["a"], ["b"], spy)
    assert second == first and cached is True
    assert spy.calls == calls_after_first  # no new external calls


def test_only_new_strings_are_transformed(tmp_path):
    service, spy = _service(tmp_path), SpyTransformer()
    service.create(["a", "b"], ["c", "d"], spy)
    assert sorted(spy.calls) == ["a", "b", "c", "d"]
    service.create(["a", "b"], ["e", "f"], spy)
    assert sorted(spy.calls) == ["a", "b", "c", "d", "e", "f"]  # only e, f added


def test_duplicate_strings_transformed_once(tmp_path):
    service, spy = _service(tmp_path), SpyTransformer()
    pid, _ = service.create(["a", "a"], ["a", "b"], spy)
    assert sorted(spy.calls) == ["a", "b"]
    assert service.get(pid) == "A, A, A, B"


def test_empty_lists(tmp_path):
    service, _ = _service(tmp_path), SpyTransformer()
    pid, _ = service.create([], [], SpyTransformer())
    assert service.get(pid) == ""


def test_length_mismatch_raises(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(ValueError):
        service.create(["a"], ["a", "b"], SpyTransformer())


def test_collision_is_detected(tmp_path, monkeypatch):
    service = _service(tmp_path)
    monkeypatch.setattr(hashing, "payload_id", lambda *a, **k: "fixed")
    # Patch the name imported into the service module too.
    monkeypatch.setattr("payload_cache.services.payload.payload_id", lambda *a, **k: "fixed")
    service.create(["a"], ["b"], SpyTransformer())
    with pytest.raises(PayloadCollisionError):
        service.create(["x"], ["y"], SpyTransformer())
