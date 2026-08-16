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

The `GET /admin/stock` tests below (catalog-wide triage list) additionally
prove: auth gates before any repository/reader call; the response carries
product name/slug/model per variant row; `quantities_for_variants` is
called exactly once regardless of product/variant count (no N+1, design.md
"one bulk stock query"); `?below`/`?search` reach the use case and affect
the response; omitting both returns every variant; and a bulk-read failure
propagates to a framework-default `500` with no `_execute_or_raise`
involvement (D6).
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest
from admin_jwt_integration_support import make_valid_admin_token
from fastapi.testclient import TestClient

from gcell.main import app
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.stock.application.stock_movement_history_reader import RecordedStockMovement
from gcell.stock.domain.stock_movement import MovementType, StockMovement
from gcell.stock.infrastructure.postgres_stock_level_reader import PostgresStockLevelReader
from gcell.stock.infrastructure.postgres_stock_movement_history_reader import (
    PostgresStockMovementHistoryReader,
)
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


def make_product(
    *, name: str = "Funda iPhone 15", variants: list[ProductVariant] | None = None
) -> Product:
    return Product(
        id=uuid4(),
        slug=f"funda-iphone-15-{uuid4().hex[:8]}",
        name=name,
        model=name,
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
        PostgresStockLevelReader,
        "quantities_for_variants",
        _spy(calls, "stock_reader.quantities_for_variants"),
    )
    monkeypatch.setattr(
        PostgresStockMovementRepository, "record", _spy(calls, "movement_repo.record")
    )
    monkeypatch.setattr(
        PostgresStockMovementHistoryReader,
        "list_for_variant",
        _spy(calls, "history_reader.list_for_variant"),
    )


_STOCK_ROUTES = [
    pytest.param("GET", lambda pid, vid: f"/admin/products/{pid}/stock", None, id="get-stock"),
    pytest.param(
        "POST",
        lambda pid, vid: f"/admin/products/{pid}/variants/{vid}/stock/movements",
        {"movement_type": "restock", "quantity_delta": 5},
        id="post-movement",
    ),
    pytest.param(
        "GET",
        lambda pid, vid: f"/admin/products/{pid}/variants/{vid}/stock/movements",
        None,
        id="get-movement-history",
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

    async def fake_quantities_for_variants(self, variant_ids):
        return {vid: 0 for vid in variant_ids}

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )
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


def test_get_stock_calls_bulk_reader_exactly_once_regardless_of_variant_count(
    monkeypatch,
) -> None:
    variants = [make_variant("Negro"), make_variant("Azul"), make_variant("Rojo")]
    product = make_product(variants=variants)
    calls: list[str] = []

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    async def fake_quantities_for_variants(self, variant_ids):
        calls.append("stock_reader.quantities_for_variants")
        return {vid: 7 for vid in variant_ids}

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product.id}/stock",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert len(response.json()) == 3
    assert calls == ["stock_reader.quantities_for_variants"]


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

    async def fake_quantities_for_variants(self, variant_ids):
        return {
            vid: sum(m.quantity_delta for m in movements if m.variant_id == vid)
            for vid in variant_ids
        }

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresStockMovementRepository, "record", fake_record)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )
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


def make_recorded_movement(variant_id, movement_id: int) -> RecordedStockMovement:
    return RecordedStockMovement(
        id=movement_id,
        variant_id=variant_id,
        movement_type=MovementType.RESTOCK,
        quantity_delta=1,
        reason=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_get_movement_history_for_foreign_variant_id_returns_404_never_403(monkeypatch) -> None:
    product_a = make_product()
    product_b = make_product()

    async def fake_get_by_id(self, product_id):
        return product_a if product_id == product_a.id else None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product_a.id}/variants/{product_b.variants[0].id}"
            "/stock/movements",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_get_movement_history_for_unknown_variant_id_returns_404(monkeypatch) -> None:
    product = make_product()

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product.id}/variants/{uuid4()}/stock/movements",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_get_movement_history_for_variant_with_no_movements_returns_empty_page(
    monkeypatch,
) -> None:
    variant = make_variant()
    product = make_product(variants=[variant])

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    async def fake_list_for_variant(self, variant_id, limit, before_id):
        return []

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresStockMovementHistoryReader, "list_for_variant", fake_list_for_variant
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product.id}/variants/{variant.id}/stock/movements",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_before_id": None}


def test_get_movement_history_limit_above_cap_is_clamped_not_rejected(monkeypatch) -> None:
    variant = make_variant()
    product = make_product(variants=[variant])
    captured_limits: list[int] = []

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    async def fake_list_for_variant(self, variant_id, limit, before_id):
        captured_limits.append(limit)
        return []

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresStockMovementHistoryReader, "list_for_variant", fake_list_for_variant
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product.id}/variants/{variant.id}/stock/movements?limit=500",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert captured_limits == [101]  # clamped to 100, then +1 trim request


def test_get_movement_history_invalid_before_id_returns_422_not_500(monkeypatch) -> None:
    variant = make_variant()
    product = make_product(variants=[variant])

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product.id}/variants/{variant.id}/stock/movements"
            "?before_id=abc",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422


def test_get_movement_history_second_page_items_are_strictly_older_than_first_page(
    monkeypatch,
) -> None:
    variant = make_variant()
    product = make_product(variants=[variant])
    all_movements = [make_recorded_movement(variant.id, i) for i in range(1, 4)]  # ids 1, 2, 3

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    async def fake_list_for_variant(self, variant_id, limit, before_id):
        rows = [m for m in all_movements if before_id is None or m.id < before_id]
        rows.sort(key=lambda m: m.id, reverse=True)
        return rows[:limit]

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresStockMovementHistoryReader, "list_for_variant", fake_list_for_variant
    )
    token = make_valid_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    base_path = f"/admin/products/{product.id}/variants/{variant.id}/stock/movements"

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        page_one = client.get(f"{base_path}?limit=2", headers=headers)
        next_before_id = page_one.json()["next_before_id"]
        page_two = client.get(f"{base_path}?limit=2&before_id={next_before_id}", headers=headers)

    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert set(page_one.json().keys()) == {"items", "next_before_id"}
    first_page_min_id = min(item["id"] for item in page_one.json()["items"])
    second_page_ids = [item["id"] for item in page_two.json()["items"]]
    assert second_page_ids
    assert all(item_id < first_page_min_id for item_id in second_page_ids)


# ---------------------------------------------------------------------------
# GET /admin/stock -- catalog-wide triage list (design.md "Endpoints";
# spec: admin-api-access "GET /admin/stock Endpoint", admin-stock-management
# "Catalog-Wide Stock Triage Ordering, Threshold, And Search").
# ---------------------------------------------------------------------------


def test_no_token_on_list_stock_route_returns_401_and_never_calls_repository(
    monkeypatch,
) -> None:
    calls: list[str] = []

    async def fake_list_all(self):
        calls.append("product_repo.list_all")
        return []

    async def fake_quantities_for_variants(self, variant_ids):
        calls.append("stock_reader.quantities_for_variants")
        return {}

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )

    with TestClient(app) as client:
        response = client.get("/admin/stock")

    assert response.status_code == 401
    assert calls == []


def test_list_stock_returns_rows_with_product_context(monkeypatch) -> None:
    variant = make_variant("Negro")
    product = make_product(variants=[variant])

    async def fake_list_all(self):
        return [product]

    async def fake_quantities_for_variants(self, variant_ids):
        return {variant_id: 3 for variant_id in variant_ids}

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get("/admin/stock", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "product_id": str(product.id),
            "product_slug": product.slug,
            "product_name": product.name,
            "product_model": product.model,
            "variant_id": str(variant.id),
            "color": variant.color,
            "quantity_on_hand": 3,
        }
    ]


def test_list_stock_calls_bulk_stock_reader_exactly_once_regardless_of_variant_count(
    monkeypatch,
) -> None:
    products = [
        make_product(variants=[make_variant("Negro"), make_variant("Blanco")]) for _ in range(3)
    ]

    async def fake_list_all(self):
        return products

    calls: list[list] = []

    async def spying_quantities_for_variants(self, variant_ids):
        calls.append(list(variant_ids))
        return {variant_id: 0 for variant_id in variant_ids}

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", spying_quantities_for_variants
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get("/admin/stock", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(calls) == 1
    assert len(calls[0]) == 6  # 3 products * 2 variants each
    assert len(response.json()) == 6


def test_list_stock_omitting_below_and_search_returns_every_variant(monkeypatch) -> None:
    products = [
        make_product(variants=[make_variant("Negro")]),
        make_product(variants=[make_variant("Blanco")]),
    ]

    async def fake_list_all(self):
        return products

    async def fake_quantities_for_variants(self, variant_ids):
        return {variant_id: 1 for variant_id in variant_ids}

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get("/admin/stock", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_stock_below_query_param_narrows_the_response(monkeypatch) -> None:
    variant_low = make_variant("Negro")
    variant_high = make_variant("Blanco")
    product = make_product(variants=[variant_low, variant_high])

    async def fake_list_all(self):
        return [product]

    async def fake_quantities_for_variants(self, variant_ids):
        return {variant_low.id: 0, variant_high.id: 10}

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            "/admin/stock?below=0", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    body = response.json()
    assert [row["variant_id"] for row in body] == [str(variant_low.id)]


def test_list_stock_search_query_param_narrows_the_response(monkeypatch) -> None:
    matching_product = make_product(name="Funda Silicona", variants=[make_variant("Negro")])
    other_product = make_product(name="Cargador Rapido", variants=[make_variant("Blanco")])

    async def fake_list_all(self):
        return [matching_product, other_product]

    async def fake_quantities_for_variants(self, variant_ids):
        return {variant_id: 0 for variant_id in variant_ids}

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            "/admin/stock?search=funda", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    body = response.json()
    assert [row["product_name"] for row in body] == [matching_product.name]


def test_list_stock_bulk_read_failure_returns_500_with_no_execute_or_raise(monkeypatch) -> None:
    product = make_product()

    async def fake_list_all(self):
        return [product]

    async def failing_quantities_for_variants(self, variant_ids):
        raise asyncpg.PostgresConnectionError("connection lost")

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", failing_quantities_for_variants
    )
    token = make_valid_admin_token()

    with TestClient(app, raise_server_exceptions=False) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get("/admin/stock", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 500
