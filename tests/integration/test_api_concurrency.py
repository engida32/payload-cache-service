"""Concurrent identical requests must not pay the transformer twice."""

from concurrent.futures import ThreadPoolExecutor
from time import sleep

from fastapi.testclient import TestClient

from payload_cache.api.deps import get_transformer
from payload_cache.main import create_app

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
DISTINCT = 6


class SlowSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def transform(self, value: str) -> str:
        self.calls.append(value)
        sleep(0.05)
        return value.upper()

    def transform_batch(self, values: list[str]) -> list[str]:
        return [self.transform(value) for value in values]


def test_simultaneous_requests_share_one_build(engine):
    spy = SlowSpy()
    app = create_app(engine)
    app.dependency_overrides[get_transformer] = lambda: spy

    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(
                pool.map(lambda _: client.post("/payload", json=SAMPLE), range(8))
            )

    bodies = [response.json() for response in responses]
    assert {body["id"] for body in bodies} == {bodies[0]["id"]}
    assert [body["cached"] for body in bodies].count(False) == 1
    assert len(spy.calls) == DISTINCT
    assert len(set(spy.calls)) == DISTINCT
