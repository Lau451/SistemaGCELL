"""Integration tests for the `/admin` router: proves dependency ORDER (auth
precedes the DB-pool guard) and the proof endpoint's happy path via
`TestClient`. Never touches a live Supabase Auth service or a live
Postgres -- `conftest.py`'s JWKS stub covers auth, and
`PostgresProductRepository.list_all` is monkeypatched as a spy (per
design.md's Testing Strategy) for the 200 case.
"""

from uuid import uuid4

from admin_jwt_integration_support import make_valid_admin_token
from fastapi.testclient import TestClient

from gcell.main import app
from gcell.products.domain.product import Product
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)


class _FakeAcquireCtx:
    async def __aenter__(self):
        return object()  # dummy connection -- unused, `list_all` is monkeypatched below

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquireCtx()

    async def close(self) -> None:
        # `main.py`'s lifespan teardown calls `close_pool` unconditionally
        # on exit; this fake pool is swapped in mid-test, after startup.
        pass


def test_bad_token_with_no_pool_returns_401_not_503(monkeypatch) -> None:
    # Order proof: auth MUST run before the pool guard, so a bad token
    # never lets a caller learn whether the DB is available.
    monkeypatch.delenv("DB_URL", raising=False)
    calls: list[None] = []
    monkeypatch.setattr(
        PostgresProductRepository,
        "list_all",
        lambda self: calls.append(None),
    )

    with TestClient(app) as client:
        response = client.get("/admin/products", headers={"Authorization": "Bearer not-a-real-jwt"})

    assert response.status_code == 401
    assert calls == []


def test_valid_token_with_no_pool_returns_503(monkeypatch) -> None:
    monkeypatch.delenv("DB_URL", raising=False)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        response = client.get("/admin/products", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 503


def test_valid_token_with_pool_returns_200_with_product_rows(monkeypatch) -> None:
    monkeypatch.delenv("DB_URL", raising=False)
    token = make_valid_admin_token()

    product = Product(id=uuid4(), slug="test-product", name="Test Product", model="TP-1")

    async def fake_list_all(self) -> list[Product]:
        return [product]

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get("/admin/products", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "id": str(product.id),
            "slug": "test-product",
            "name": "Test Product",
            "model": "TP-1",
            "variants": [],
        }
    ]
