"""FastAPI application entrypoint.

Composition-root only: wires the app and its routers. No business logic
lives here — that belongs in each domain's `application`/`domain` layers.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gcell.api.admin import router as admin_router
from gcell.api.health import router as health_router
from gcell.shared.infrastructure.config import db_url
from gcell.shared.infrastructure.postgres import close_pool, create_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    dsn = db_url()
    if dsn is None:
        # `/health` never needs the pool, and `/admin/*` is guarded by
        # `require_db_pool` (503 when `None`) -- see design.md "Decision:
        # per-request 503 dependency guard, not startup abort". Only those
        # two route groups exist, so a missing `DB_URL` here is safe to log
        # and continue rather than fail startup.
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
app.include_router(admin_router)
