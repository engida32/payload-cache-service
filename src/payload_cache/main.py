"""App factory + module-level `app` for uvicorn."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from payload_cache.api.routes import router
from payload_cache.db.session import get_engine, init_db


def create_app(engine: Engine | None = None) -> FastAPI:
    db_engine = engine if engine is not None else get_engine()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        init_db(db_engine)
        yield

    app = FastAPI(title="Payload Cache Service", version="0.1.0", lifespan=lifespan)
    app.state.engine = db_engine
    app.include_router(router)
    return app


app = create_app()
