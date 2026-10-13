import socket
import threading
import time

import pytest
import uvicorn

from payload_cache.cli.main import main
from payload_cache.db.session import create_db_engine
from payload_cache.main import create_app

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'cli.db'}")
    app = create_app(engine)
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    proc = uvicorn.Server(config)

    thread = threading.Thread(target=proc.run, daemon=True)
    thread.start()
    for _ in range(100):
        if proc.started:
            break
        time.sleep(0.05)
    else:
        pytest.fail("server did not start")
    yield f"http://127.0.0.1:{port}"
    proc.should_exit = True
    thread.join(timeout=5)


def test_cli_round_trip(server, tmp_path):
    out = tmp_path / "out.txt"
    payload = '{"list_1":["a","b"],"list_2":["c","d"]}'
    with pytest.raises(SystemExit) as excinfo:
        main(["--host", server, "--json", payload, "--repeat", "2", "--output", str(out)])
    assert excinfo.value.code == 0
    assert out.read_text().splitlines() == ["A, C, B, D", "A, C, B, D"]
