"""Integration tests for `shared.infrastructure.postgres.transaction()`.

Exercises both branches directly against real local Postgres:

- Given a `Pool`, `transaction()` acquires a connection and issues a real
  BEGIN/COMMIT (or ROLLBACK on exception) -- unlike `db_conn`, which is a
  `Connection` already inside a transaction that is always rolled back by
  the fixture, so it can only prove the nested-SAVEPOINT branch (exercised
  implicitly by `test_product_repository.py`'s use of `PostgresProductRepository`,
  which is handed `db_conn` directly).
- Because the pool-branch tests really commit, they clean up manually --
  they are not protected by `db_conn`'s outer rollback.
"""

from uuid import uuid4

import pytest

from gcell.shared.infrastructure.postgres import transaction


async def test_transaction_with_pool_commits_on_clean_exit(db_pool) -> None:
    slug = f"tx-helper-commit-{uuid4().hex}"
    try:
        async with transaction(db_pool) as conn:
            await conn.execute(
                "INSERT INTO products (id, slug, name, model) VALUES ($1, $2, $3, $4)",
                uuid4(),
                slug,
                "Tx Helper Product",
                "Model X",
            )

        async with db_pool.acquire() as verify_conn:
            row = await verify_conn.fetchrow(
                "SELECT slug FROM products WHERE slug = $1", slug
            )
        assert row is not None
    finally:
        async with db_pool.acquire() as cleanup_conn:
            await cleanup_conn.execute("DELETE FROM products WHERE slug = $1", slug)


async def test_transaction_with_pool_rolls_back_on_exception(db_pool) -> None:
    slug = f"tx-helper-rollback-{uuid4().hex}"

    with pytest.raises(RuntimeError):
        async with transaction(db_pool) as conn:
            await conn.execute(
                "INSERT INTO products (id, slug, name, model) VALUES ($1, $2, $3, $4)",
                uuid4(),
                slug,
                "Tx Helper Product",
                "Model X",
            )
            raise RuntimeError("boom")

    async with db_pool.acquire() as verify_conn:
        row = await verify_conn.fetchrow(
            "SELECT slug FROM products WHERE slug = $1", slug
        )
    assert row is None


async def test_transaction_with_connection_becomes_a_savepoint(db_conn) -> None:
    """Given an already-in-transaction `Connection`, `transaction()` must not
    issue a second top-level BEGIN -- asyncpg turns the nested
    `Connection.transaction()` into a SAVEPOINT, so the code under test can
    commit its savepoint while the outer `db_conn` rollback still erases it.
    """
    slug = f"tx-helper-savepoint-{uuid4().hex}"

    async with transaction(db_conn) as conn:
        assert conn is db_conn
        await conn.execute(
            "INSERT INTO products (id, slug, name, model) VALUES ($1, $2, $3, $4)",
            uuid4(),
            slug,
            "Tx Helper Product",
            "Model X",
        )

    row = await db_conn.fetchrow("SELECT slug FROM products WHERE slug = $1", slug)
    assert row is not None
