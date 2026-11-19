"""Print a miss/hit/partial transcript against the real service in-process."""

from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from fastapi.testclient import TestClient

from payload_cache.api.deps import get_transformer
from payload_cache.db.session import create_db_engine, init_db
from payload_cache.main import create_app
from payload_cache.services.transformer import UppercaseTransformer

LATENCY_MS = 25

BASE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
EXTENDED = {
    "list_1": BASE["list_1"] + ["fourth string", "fifth string"],
    "list_2": BASE["list_2"] + ["extra string", "final string"],
}


def run(client: TestClient, transformer: UppercaseTransformer, label: str, body: dict) -> None:
    calls_before = transformer.call_count
    started = perf_counter()
    response = client.post("/payload", json=body)
    elapsed_ms = (perf_counter() - started) * 1000
    data = response.json()
    print(
        f"{label:<22} {elapsed_ms:7.1f} ms  "
        f"cached={str(data['cached']).lower():<5} "
        f"transformer calls={transformer.call_count - calls_before}"
    )


def main() -> None:
    with TemporaryDirectory() as tmp:
        db = Path(tmp) / "bench.db"
        engine = create_db_engine(f"sqlite:///{db}")
        init_db(engine)
        transformer = UppercaseTransformer(latency_ms=LATENCY_MS)
        app = create_app(engine)
        app.dependency_overrides[get_transformer] = lambda: transformer
        with TestClient(app) as client:
            print(f"transformer latency: {LATENCY_MS} ms per string")
            run(client, transformer, "1 miss (3+3)", BASE)
            run(client, transformer, "2 repeat (3+3)", BASE)
            run(client, transformer, "3 partial (5+5)", EXTENDED)


if __name__ == "__main__":
    main()
