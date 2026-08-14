"""Per-request DB pool / Storage config availability guards.

Scoped to `/admin` routes only -- see design.md's "Decision: per-request
503 dependency guard, not startup abort". `lifespan` already tolerates a
`None` pool when `DB_URL` is unset (`main.py`); `/health` and its tests
never depend on the pool at all. `require_db_pool` is the ONLY thing that
turns "pool absent" into a rejected request, and only for routes that
declare it. `require_storage` is the same pattern for Supabase Storage
config (design.md "Config": "New `require_storage` dependency mirrors
require_db_pool -> 503 storage_unavailable").
"""

from dataclasses import dataclass

import asyncpg
from fastapi import HTTPException, Request

from gcell.shared.infrastructure.config import supabase_service_role_key, supabase_url


def require_db_pool(request: Request) -> asyncpg.Pool:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database_unavailable")
    return pool


@dataclass(frozen=True)
class StorageCredentials:
    """Supabase Storage config resolved from the environment (see
    `config.supabase_url`/`config.supabase_service_role_key`) -- what a
    `shared/infrastructure/supabase_storage.py` adapter needs to be
    constructed. Read fresh per request, same as `verify_admin_jwt`
    reading `jwks_url()`/`jwt_issuer()` directly, rather than cached at
    startup on `app.state` -- these are plain env reads, not a pooled
    resource like `asyncpg.Pool`.
    """

    url: str
    service_role_key: str


def require_storage() -> StorageCredentials:
    url = supabase_url()
    service_role_key = supabase_service_role_key()
    if url is None or service_role_key is None:
        raise HTTPException(status_code=503, detail="storage_unavailable")
    return StorageCredentials(url=url, service_role_key=service_role_key)
