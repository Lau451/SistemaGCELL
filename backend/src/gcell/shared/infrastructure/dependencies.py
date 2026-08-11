"""Per-request DB pool availability guard.

Scoped to `/admin` routes only -- see design.md's "Decision: per-request
503 dependency guard, not startup abort". `lifespan` already tolerates a
`None` pool when `DB_URL` is unset (`main.py`); `/health` and its tests
never depend on the pool at all. This dependency is the ONLY thing that
turns "pool absent" into a rejected request, and only for routes that
declare it.
"""

import asyncpg
from fastapi import HTTPException, Request


def require_db_pool(request: Request) -> asyncpg.Pool:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database_unavailable")
    return pool
