"""Integration tests for the FastAPI `lifespan` -> `app.state.db_pool` wiring.

`TestClient` must be used as a context manager (`with TestClient(app) as
client:`) for lifespan to run at all -- see `test_health.py`'s own fix and
design.md's explicit warning that a broken lifespan would otherwise ship
green.
"""

import asyncpg
from fastapi.testclient import TestClient

from gcell.main import app


def test_db_pool_is_none_when_db_url_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("DB_URL", raising=False)

    with TestClient(app) as client:
        assert client.app.state.db_pool is None


async def test_db_pool_is_created_and_closed_when_db_url_is_set(monkeypatch) -> None:
    monkeypatch.setenv(
        "DB_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    )

    with TestClient(app) as client:
        pool = client.app.state.db_pool
        assert isinstance(pool, asyncpg.Pool)
        assert not pool.is_closing()

    assert pool.is_closing()
