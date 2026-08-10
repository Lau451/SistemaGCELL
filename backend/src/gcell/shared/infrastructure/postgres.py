"""Postgres pool lifecycle and the single cross-domain transaction seam.

`shared/` must never import from `products/` or `stock/` (wrong dependency
direction) -- this module only knows about `asyncpg`, never about any
domain's ports or entities. Repositories receive a `Connection` by
constructor injection, never `Depends` and never the `Pool` itself -- see
design.md "transaction boundary at the composition root".
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg


async def create_pool(dsn: str) -> asyncpg.Pool:
    """Create the app-wide pool.

    `min_size=0` so startup opens no socket -- `/health` and tests never
    require Postgres to be reachable just to boot the app.
    """
    return await asyncpg.create_pool(dsn, min_size=0, max_size=10)


async def close_pool(pool: asyncpg.Pool) -> None:
    await pool.close()


@asynccontextmanager
async def transaction(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection,
) -> AsyncIterator[asyncpg.Connection]:
    """Yield a connection inside a transaction, regardless of what it is given.

    - Given a `Pool`: acquires a connection and issues a real BEGIN; COMMIT
      on clean exit, ROLLBACK on exception.
    - Given a `Connection` that is already inside a transaction (e.g. a
      test's `db_conn` fixture): asyncpg turns the nested
      `Connection.transaction()` into a SAVEPOINT, so the code under test
      commits its savepoint while an outer rollback still erases everything.
    """
    if isinstance(pool_or_conn, asyncpg.Pool):
        async with pool_or_conn.acquire() as conn, conn.transaction():
            yield conn
    else:
        async with pool_or_conn.transaction():
            yield pool_or_conn
