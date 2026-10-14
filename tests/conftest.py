import pytest
from fastapi.testclient import TestClient

from payload_cache.api.deps import get_transformer
from payload_cache.db.session import create_db_engine, init_db
from payload_cache.main import create_app


class SpyTransformer:
    def __init__(self):
        self.calls: list[str] = []

    def transform(self, value: str) -> str:
        self.calls.append(value)
        return value.upper()

    def transform_batch(self, values: list[str]) -> list[str]:
        return [self.transform(v) for v in values]


@pytest.fixture
def engine(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'api.db'}")
    init_db(engine)
    return engine


@pytest.fixture
def spy():
    return SpyTransformer()


@pytest.fixture
def client(engine, spy):
    app = create_app(engine)
    app.dependency_overrides[get_transformer] = lambda: spy
    with TestClient(app) as test_client:
        yield test_client
