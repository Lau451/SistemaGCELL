"""Integration tests for the `/admin` stock routes.

Mirrors `test_admin_images.py`'s conventions: `TestClient`,
`admin_jwt_integration_support`'s forged token, and monkeypatched-spy
adapters -- never a live Supabase Auth service or a live Postgres. Proves
the router-level `Depends(verify_admin_jwt)` auth gate, the IDOR ownership
guard (404, never a distinguishable body, for a foreign `variant_id`), the
domain validation that runs before any write (`422` for a wrong-sign delta,
an unknown `movement_type`, a zero delta, or a blank `reason`, all with zero
`stock_movements` inserts), `extra="forbid"` on the request body, that
`reason` is optional for every movement type, and that a GET after two
POSTs reflects the recorded movements' running sum (spec:
admin-stock-management, admin-api-access).
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from admin_jwt_integration_support import make_valid_admin_token
from fastapi.testclient import TestClient

from gcell.main import app
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.stock.domain.stock_movement import StockMovement
from gcell.stock.infrastructure.postgres_stock_level_reader import PostgresStockLevelReader
from gcell.stock.infrastructure.postgres_stock_movement_repository import (
    PostgresStockMovementRepository,
)


class _FakeAcquireCtx:
    async def __aenter__(self):
        return object()  # dummy connection -- every adapter method below is monkeypatched

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquireCtx()

    async def close(self) -> None:
        pass


def make_variant(color: str = "Negro") -> ProductVariant:
    return ProductVariant(
        id=uuid4(), color=color, price=Decimal("45000.00"), cost=Decimal("30000.00")
    )


def make_product(*, variants: list[ProductVariant] | None = None) -> Product:
    return Product(
        id=uuid4(),
        slug=f"funda-iphone-15-{uuid4().hex[:8]}",
        name="Funda iPhone 15",
        model="Funda iPhone 15",
        variants=variants if variants is not None else [make_variant()],
    )


def _spy(calls: list[str], label: str):
    async def _fn(self, *args, **kwargs):
        calls.append(label)

    return _fn


def _spy_all_adapters(monkeypatch, calls: list[str]) -> None:
    monkeypatch.setattr(
        PostgresProductRepository, "get_by_id", _spy(calls, "product_repo.get_by_id")
    )
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantity_on_hand", _spy(calls, "stock_reader.quantity_on_hand")
    )
    monkeypatch.setattr(
        PostgresStockMovementRepository, "record", _spy(calls, "movement_repo.record")
    )


_STOCK_ROUTES = [
    pytest.param("GET", lambda pid, vid: f"/admin/products/{pid}/stock", None, id="get-stock"),
    pytest.param(
        "POST",
        lambda pid, vid: f"/admin/products/{pid}/variants/{vid}/stock/movements",
        {"movement_type": "restock", "quantity_delta": 5},
        id="post-movement",
    ),
]


@pytest.mark.parametrize(("method", "path_fn", "body"), _STOCK_ROUTES)
def test_no_token_on_stock_routes_returns_401_and_never_calls_repository(
    monkeypatch, method: str, path_fn, body: dict | None
) -> None:
    calls: list[str] = []
    _spy_all_adapters(monkeypatch, calls)
    product_id = uuid4()
    variant_id = uuid4()

    with TestClient(app) as client:
        response = client.request(method, path_fn(product_id, variant_id), json=body)

    assert response.status_code == 401
    assert calls == []


def test_get_stock_for_unknown_product_returns_404(monkeypatch) -> None:
    async def fake_get_by_id(self, product_id):
        return None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{uuid4()}/stock",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_get_stock_for_variant_with_no_movements_returns_zero(monkeypatch) -> None:
    variant = make_variant()
    product = make_product(variants=[variant])

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    async def fake_quantity_on_hand(self, variant_id):
        return 0

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresStockLevelReader, "quantity_on_hand", fake_quantity_on_hand)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product.id}/stock",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == [
        {"variant_id": str(variant.id), "color": variant.color, "quantity_on_hand": 0}
    ]


def test_post_movement_with_foreign_variant_id_returns_404_and_zero_writes(monkeypatch) -> None:
    product_a = make_product()
    product_b = make_product()
    calls: list[str] = []

    async def fake_get_by_id(self, product_id):
        return product_a if product_id == product_a.id else None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresStockMovementRepository, "record", _spy(calls, "movement_repo.record")
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product_a.id}/variants/{product_b.variants[0].id}"
            "/stock/movements",
            json={"movement_type": "restock", "quantity_delta": 5},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}
    assert calls == []


_INVALID_BODIES = [
    pytest.param({"movement_type": "sale", "quantity_delta": 5}, id="wrong-sign"),
    pytest.param({"movement_type": "theft", "quantity_delta": 5}, id="unknown-type"),
    pytest.param({"movement_type": "restock", "quantity_delta": 0}, id="zero-delta"),
    pytest.param(
        {"movement_type": "restock", "quantity_delta": 5, "reason": "   "}, id="blank-reason"
    ),
    pytest.param(
        {"movement_type": "restock", "quantity_delta": 5, "extra_field": "nope"},
        id="extra-field",
    ),
]


@pytest.mark.parametrize("body", _INVALID_BODIES)
def test_post_movement_invalid_body_returns_422_and_zero_writes(monkeypatch, body: dict) -> None:
    variant = make_variant()
    product = make_product(variants=[variant])
    calls: list[str] = []

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresStockMovementRepository, "record", _spy(calls, "movement_repo.record")
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product.id}/variants/{variant.id}/stock/movements",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    assert calls == []


def test_post_adjustment_with_no_reason_succeeds(monkeypatch) -> None:
    variant = make_variant()
    product = make_product(variants=[variant])
    recorded: list[StockMovement] = []

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    async def fake_record(self, movement):
        recorded.append(movement)

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresStockMovementRepository, "record", fake_record)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product.id}/variants/{variant.id}/stock/movements",
            json={"movement_type": "adjustment", "quantity_delta": -2},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "variant_id": str(variant.id),
        "movement_type": "adjustment",
        "quantity_delta": -2,
        "reason": None,
    }
    assert len(recorded) == 1
    assert recorded[0].reason is None


def test_post_then_get_readback_reflects_the_running_sum(monkeypatch) -> None:
    variant = make_variant()
    product = make_product(variants=[variant])
    movements: list[StockMovement] = []

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    async def fake_record(self, movement):
        movements.append(movement)

    async def fake_quantity_on_hand(self, variant_id):
        return sum(m.quantity_delta for m in movements if m.variant_id == variant_id)

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresStockMovementRepository, "record", fake_record)
    monkeypatch.setattr(PostgresStockLevelReader, "quantity_on_hand", fake_quantity_on_hand)
    token = make_valid_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    movement_path = f"/admin/products/{product.id}/variants/{variant.id}/stock/movements"

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()

        restock_response = client.post(
            movement_path,
            json={"movement_type": "restock", "quantity_delta": 10},
            headers=headers,
        )
        sale_response = client.post(
            movement_path,
            json={"movement_type": "sale", "quantity_delta": -3},
            headers=headers,
        )
        stock_response = client.get(f"/admin/products/{product.id}/stock", headers=headers)

    assert restock_response.status_code == 201
    assert sale_response.status_code == 201
    assert stock_response.status_code == 200
    assert stock_response.json() == [
        {"variant_id": str(variant.id), "color": variant.color, "quantity_on_hand": 7}
    ]
