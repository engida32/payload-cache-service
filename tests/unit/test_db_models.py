from sqlmodel import Session, select

from payload_cache.db.models import Payload, TransformCache
from payload_cache.db.session import create_db_engine, init_db


def test_create_and_read_rows(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_db(engine)
    with Session(engine) as session:
        session.add(TransformCache(version=1, key="a", value="A"))
        session.add(Payload(id="pid", input_json="{}", output="A"))
        session.commit()
        assert session.exec(select(TransformCache)).one().value == "A"
        assert session.get(Payload, "pid").output == "A"
