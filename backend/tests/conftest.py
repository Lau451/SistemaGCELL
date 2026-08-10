"""Shared pytest fixtures for integration tests against a real Postgres.

Function-scoped pool (avoids pytest-asyncio session-loop/`loop_scope`
friction at this suite size — see design.md "Testing Strategy").
`db_conn` gives every DB-touching test a per-test rollback boundary: it
starts a real transaction on an acquired connection and rolls it back after
the test, so tests are ordering-independent and leave no rows — any nested
`transaction()` call the code under test makes becomes a SAVEPOINT that
commits into the still-uncommitted outer transaction, which is then erased.
"""

import os

import asyncpg
import pytest


@pytest.fixture
async def db_pool():
    dsn = os.environ.get("DB_URL")
    if not dsn:
        pytest.skip("DB_URL not set -- run `npx supabase start`")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def db_conn(db_pool):
    async with db_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
        finally:
            await tx.rollback()
