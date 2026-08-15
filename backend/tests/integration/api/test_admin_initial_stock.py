"""Integration tests for `POST /admin/products`' `initial_quantity` support
(spec: "Product Creation Accepts An Optional Initial Quantity Per Variant").

Follows `test_admin.py`'s monkeypatched-spy convention for the 201/422/PATCH
cases (2.2) -- `_FakePool` (Decision 3) makes the route's new
`transaction(pool)` wiring work with a fake, monkeypatched
`PostgresProductRepository`/`PostgresStockMovementRepository`. The atomicity
case (2.4) needs a REAL `db_pool` and `TestClient`, same precedent as
`test_admin.py::test_delete_variant_cross_parent_returns_404_not_403` -- a
spy cannot prove the route's `transaction(pool)` scope actually rolls back
on a mid-composition failure.
"""

from decimal import Decimal
from uuid import uuid4

from admin_jwt_integration_support import make_valid_admin_token
from fastapi.testclient import TestClient

from gcell.main import app
from gcell.products.domain.product import Product
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.stock.application.exceptions import UnknownVariantError
from gcell.stock.domain.stock_movement import MovementType, StockMovement
from gcell.stock.infrastructure.postgres_stock_movement_repository import (
    PostgresStockMovementRepository,
)


class _FakeAcquireCtx:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquireCtx()

    def transaction(self):
        return _FakeAcquireCtx()

    async def close(self) -> None:
        pass


def test_positive_initial_quantity_returns_201_and_records_one_restock_movement(
    monkeypatch,
) -> None:
    added: list[Product] = []
    recorded: list[StockMovement] = []

    async def fake_slug_exists(self, slug: str) -> bool:
        return False

    async def fake_add(self, product: Product) -> None:
        added.append(product)

    async def fake_record(self, movement: StockMovement) -> None:
        recorded.append(movement)

    monkeypatch.setattr(PostgresProductRepository, "slug_exists", fake_slug_exists)
    monkeypatch.setattr(PostgresProductRepository, "add", fake_add)
    monkeypatch.setattr(PostgresStockMovementRepository, "record", fake_record)
    token = make_valid_admin_token()
    body = {
        "name": "Funda iPhone 15",
        "model": "IP15",
        "variants": [
            {
                "color": "Negro",
                "price": "5000.00",
                "cost": "2000.00",
                "initial_quantity": 5,
            }
        ],
    }

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 201
    assert len(added) == 1
    assert len(recorded) == 1
    assert recorded[0].movement_type == MovementType.RESTOCK
    assert recorded[0].quantity_delta == 5
    assert recorded[0].variant_id == added[0].variants[0].id


def test_zero_initial_quantity_returns_201_and_records_no_movement(monkeypatch) -> None:
    recorded: list[StockMovement] = []

    async def fake_slug_exists(self, slug: str) -> bool:
        return False

    async def fake_add(self, product: Product) -> None:
        pass

    async def fake_record(self, movement: StockMovement) -> None:
        recorded.append(movement)

    monkeypatch.setattr(PostgresProductRepository, "slug_exists", fake_slug_exists)
    monkeypatch.setattr(PostgresProductRepository, "add", fake_add)
    monkeypatch.setattr(PostgresStockMovementRepository, "record", fake_record)
    token = make_valid_admin_token()
    body = {
        "name": "Funda iPhone 15",
        "model": "IP15",
        "variants": [
            {"color": "Negro", "price": "5000.00", "cost": "2000.00", "initial_quantity": 0}
        ],
    }

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 201
    assert recorded == []


def test_absent_initial_quantity_returns_201_and_records_no_movement(monkeypatch) -> None:
    recorded: list[StockMovement] = []

    async def fake_slug_exists(self, slug: str) -> bool:
        return False

    async def fake_add(self, product: Product) -> None:
        pass

    async def fake_record(self, movement: StockMovement) -> None:
        recorded.append(movement)

    monkeypatch.setattr(PostgresProductRepository, "slug_exists", fake_slug_exists)
    monkeypatch.setattr(PostgresProductRepository, "add", fake_add)
    monkeypatch.setattr(PostgresStockMovementRepository, "record", fake_record)
    token = make_valid_admin_token()
    body = {
        "name": "Funda iPhone 15",
        "model": "IP15",
        "variants": [{"color": "Negro", "price": "5000.00", "cost": "2000.00"}],
    }

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 201
    assert recorded == []


def test_negative_initial_quantity_returns_422_with_zero_repository_calls(
    monkeypatch,
) -> None:
    calls: list[None] = []

    monkeypatch.setattr(
        PostgresProductRepository, "add", lambda self, *a, **k: calls.append(None)
    )
    monkeypatch.setattr(
        PostgresStockMovementRepository,
        "record",
        lambda self, *a, **k: calls.append(None),
    )
    token = make_valid_admin_token()
    body = {
        "name": "Funda iPhone 15",
        "model": "IP15",
        "variants": [
            {"color": "Negro", "price": "5000.00", "cost": "2000.00", "initial_quantity": -1}
        ],
    }

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 422
    assert calls == []


def test_patch_accepts_and_ignores_initial_quantity(monkeypatch) -> None:
    # Widening from Decision 4 (design.md): `AdminVariantInput.initial_quantity`
    # is now a declared field, so PATCH -- reusing the same request model --
    # accepts (rather than 422-rejecting via `extra="forbid"`) a client
    # sending it, but never reads or acts on it: PATCH still goes through
    # `UpdateProductUseCase`, which knows nothing about stock movements.
    product_id = uuid4()
    existing = Product(id=product_id, slug="existing", name="Existing", model="M1")

    async def fake_get_by_id(self, pid):
        return existing if pid == product_id else None

    async def fake_list_all(self):
        return [existing]

    async def fake_update(self, product):
        return product

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(PostgresProductRepository, "update", fake_update)
    token = make_valid_admin_token()
    body = {
        "name": "Existing",
        "model": "M1",
        "variants": [
            {"color": "Negro", "price": "5000.00", "cost": "2000.00", "initial_quantity": 7}
        ],
    }

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.patch(
            f"/admin/products/{product_id}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 2.4 -- route-level atomicity: a real `db_pool`-backed failure mid-composition
# must roll back the WHOLE transaction (product + all variants), same
# precedent as `test_delete_variant_cross_parent_returns_404_not_403`.
# ---------------------------------------------------------------------------


async def test_second_variant_seed_failure_rolls_back_product_and_all_variants(
    db_pool, monkeypatch
) -> None:
    # `RegisterStockedProductUseCase` records movements strictly in
    # `product.variants` order, so putting the unseedable quantity on the
    # SECOND variant forces the failure AFTER the product+first-variant
    # insert already succeeded within the same `transaction(pool)` scope --
    # the one genuinely new failure mode the route's own wiring introduces
    # (design.md's Testing Strategy). Every variant id in the request is
    # server-generated inside `_to_domain_variants`, so an actual FK
    # violation cannot be forced through the public request body; this test
    # simulates the same DB-only failure mode (`UnknownVariantError`, which
    # `PostgresStockMovementRepository.record` itself raises on a real FK
    # violation) on the SECOND `record()` call, and proves the route's
    # `transaction(pool)` scope rolls back everything -- product, both
    # variants, and the first, otherwise-valid movement.
    token = make_valid_admin_token()
    body = {
        "name": f"Atomic Product {uuid4()}",
        "model": "Model Atomic",
        "variants": [
            {"color": "Negro", "price": "5000.00", "cost": "2000.00", "initial_quantity": 5},
            {"color": "Rojo", "price": "5000.00", "cost": "2000.00", "initial_quantity": 3},
        ],
    }

    call_count = {"n": 0}
    real_record = PostgresStockMovementRepository.record

    async def failing_second_record(self, movement):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise UnknownVariantError(movement.variant_id)
        return await real_record(self, movement)

    monkeypatch.setattr(PostgresStockMovementRepository, "record", failing_second_record)

    with TestClient(app) as client:
        response = client.post(
            "/admin/products",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404

    async with db_pool.acquire() as conn:
        product_count = await conn.fetchval(
            "SELECT count(*) FROM products WHERE name = $1", body["name"]
        )
        variant_count = await conn.fetchval(
            "SELECT count(*) FROM product_variants pv "
            "JOIN products p ON p.id = pv.product_id WHERE p.name = $1",
            body["name"],
        )
        movement_count = await conn.fetchval(
            "SELECT count(*) FROM stock_movements sm "
            "JOIN product_variants pv ON pv.id = sm.variant_id "
            "JOIN products p ON p.id = pv.product_id WHERE p.name = $1",
            body["name"],
        )
    assert product_count == 0
    assert variant_count == 0
    assert movement_count == 0
