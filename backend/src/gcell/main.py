"""FastAPI application entrypoint.

Composition-root only: wires the app and its routers. No business logic
lives here — that belongs in each domain's `application`/`domain` layers.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gcell.api.health import router as health_router
from gcell.shared.infrastructure.config import db_url
from gcell.shared.infrastructure.postgres import close_pool, create_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    dsn = db_url()
    if dsn is None:
        # Safe only because zero routes consume `app.state.db_pool` in this
        # change (no HTTP routes ship here) -- see design.md "pool lifecycle
        # and availability". The future admin+auth change MUST convert this
        # to fail-fast or a 503 dependency guard once a route needs the pool.
        logger.warning("DB_URL is not set -- app.state.db_pool will be None")
        app.state.db_pool = None
    else:
        app.state.db_pool = await create_pool(dsn)

    try:
        yield
    finally:
        if app.state.db_pool is not None:
            await close_pool(app.state.db_pool)


app = FastAPI(title="GCELL API", lifespan=lifespan)
app.include_router(health_router)
