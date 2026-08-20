"""Integration tests for the `/admin` router: proves dependency ORDER (auth
precedes the DB-pool guard) and the proof endpoint's happy path via
`TestClient`. Never touches a live Supabase Auth service or a live
Postgres -- `conftest.py`'s JWKS stub covers auth, and
`PostgresProductRepository.list_all` is monkeypatched as a spy (per
design.md's Testing Strategy) for the 200 case.

Write-route tests (`POST`/`PATCH`/`DELETE`) mostly follow the same
monkeypatched-spy convention. The one exception is the cross-parent IDOR
test, which needs two REAL, persisted products (see its own docstring for
why a spy cannot prove that case).
"""

from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest
from admin_jwt_integration_support import make_valid_admin_token
from fastapi.testclient import TestClient

from gcell.main import app
from gcell.products.application.create_product import CreateProductUseCase
from gcell.products.application.exceptions import (
    ProductNotFoundError,
    VariantNotFoundError,
)
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.stock.application.create_stocked_product import CreateStockedProductUseCase
from gcell.stock.infrastructure.postgres_stock_level_reader import (
    PostgresStockLevelReader,
)


class _FakeAcquireCtx:
    async def __aenter__(self):
        return object()  # dummy connection -- unused, `list_all` is monkeypatched below

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def acquire(self):
        return _FakeAcquireCtx()

    def transaction(self):
        # Additive Decision 3 fix: `shared.infrastructure.postgres.transaction()`
        # branches on `isinstance(pool_or_conn, asyncpg.Pool)`; `_FakePool` is
        # not one, so without this method the route's `transaction(pool)` call
        # would hit the `else` branch and raise `AttributeError` -> 500. Reuses
        # the same dummy connection as `acquire()` -- no real transaction
        # semantics are needed here, only the async-CM duck type.
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

    variant = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    product = Product(
        id=uuid4(),
        slug="test-product",
        name="Test Product",
        model="TP-1",
        variants=[variant],
    )

    async def fake_list_all(self) -> list[Product]:
        return [product]

    async def fake_quantities_for_variants(self, variant_ids):
        return {variant_id: 7 for variant_id in variant_ids}

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader, "quantities_for_variants", fake_quantities_for_variants
    )

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
            "variants": [
                {
                    "id": str(variant.id),
                    "color": "Negro",
                    "price": "45000.00",
                    "cost": "30000.00",
                    "quantity_on_hand": 7,
                }
            ],
        }
    ]


def test_list_admin_products_calls_bulk_stock_reader_exactly_once(monkeypatch) -> None:
    # D3: serving the whole catalog issues one stock query regardless of
    # product/variant count -- proves no N+1 loop crept in.
    monkeypatch.delenv("DB_URL", raising=False)
    token = make_valid_admin_token()

    products = [
        Product(
            id=uuid4(),
            slug=f"test-product-{i}",
            name=f"Test Product {i}",
            model="TP-1",
            variants=[
                ProductVariant(
                    id=uuid4(),
                    color="Negro",
                    price=Decimal("45000.00"),
                    cost=Decimal("30000.00"),
                ),
                ProductVariant(
                    id=uuid4(),
                    color="Blanco",
                    price=Decimal("45000.00"),
                    cost=Decimal("30000.00"),
                ),
            ],
        )
        for i in range(3)
    ]

    async def fake_list_all(self) -> list[Product]:
        return products

    calls: list[list] = []

    async def spying_quantities_for_variants(self, variant_ids):
        calls.append(list(variant_ids))
        return {variant_id: 0 for variant_id in variant_ids}

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader,
        "quantities_for_variants",
        spying_quantities_for_variants,
    )

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get("/admin/products", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(calls) == 1
    assert len(calls[0]) == 6  # 3 products * 2 variants each


def test_list_admin_products_bulk_stock_read_failure_returns_500(monkeypatch) -> None:
    # D6: no `_execute_or_raise` involvement -- an unhandled driver failure
    # propagates to FastAPI's default 500, never a partial/degraded 200 body.
    monkeypatch.delenv("DB_URL", raising=False)
    token = make_valid_admin_token()

    variant = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    product = Product(
        id=uuid4(), slug="test-product", name="Test Product", model="TP-1", variants=[variant]
    )

    async def fake_list_all(self) -> list[Product]:
        return [product]

    async def failing_quantities_for_variants(self, variant_ids):
        raise asyncpg.PostgresConnectionError("connection lost")

    monkeypatch.setattr(PostgresProductRepository, "list_all", fake_list_all)
    monkeypatch.setattr(
        PostgresStockLevelReader,
        "quantities_for_variants",
        failing_quantities_for_variants,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get("/admin/products", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 500


def test_get_admin_product_by_id_response_has_no_quantity_on_hand_key(monkeypatch) -> None:
    # D7: stock appears ONLY on GET /admin/products (list) -- GET-by-id stays
    # exactly as it was before this change.
    monkeypatch.delenv("DB_URL", raising=False)
    token = make_valid_admin_token()

    variant = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    product = Product(
        id=uuid4(), slug="test-product", name="Test Product", model="TP-1", variants=[variant]
    )

    async def fake_get_by_id(self, product_id):
        return product

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product.id}", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    body = response.json()
    assert "quantity_on_hand" not in body["variants"][0]


def test_create_admin_product_response_has_no_quantity_on_hand_key(monkeypatch) -> None:
    # D7: POST is unaffected -- the shared `AdminProductResponse` model is
    # untouched, no fabricated stock value on a just-created variant.
    monkeypatch.delenv("DB_URL", raising=False)
    token = make_valid_admin_token()
    created_variant = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    created_product = Product(
        id=uuid4(),
        slug="test-product",
        name="Test Product",
        model="TP-1",
        variants=[created_variant],
    )

    async def fake_execute(self, **kwargs):
        return created_product

    monkeypatch.setattr(CreateStockedProductUseCase, "execute", fake_execute)

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test Product", "model": "TP-1", "variants": []},
        )

    assert response.status_code == 201
    body = response.json()
    assert "quantity_on_hand" not in body["variants"][0]


# ---------------------------------------------------------------------------
# Write routes: POST /admin/products, PATCH /admin/products/{id},
# DELETE /admin/products/{id}, DELETE /admin/products/{id}/variants/{vid}
# ---------------------------------------------------------------------------

_WRITE_ROUTES = [
    pytest.param(
        "POST",
        "/admin/products",
        {"name": "Test Product", "model": "TP-1", "variants": []},
        "add",
        id="post",
    ),
    pytest.param(
        "PATCH",
        f"/admin/products/{uuid4()}",
        {"name": "Test Product", "model": "TP-1", "variants": []},
        "update",
        id="patch",
    ),
    pytest.param(
        "DELETE",
        f"/admin/products/{uuid4()}",
        None,
        "soft_delete",
        id="delete-product",
    ),
    pytest.param(
        "DELETE",
        f"/admin/products/{uuid4()}/variants/{uuid4()}",
        None,
        "soft_delete_variant",
        id="delete-variant",
    ),
]


class _FakePool:
    def acquire(self):
        return _FakeAcquireCtx()

    def transaction(self):
        # See the file's first `_FakePool` for the full Decision 3 rationale.
        return _FakeAcquireCtx()

    async def close(self) -> None:
        pass


@pytest.mark.parametrize(("method", "path", "body", "repo_method"), _WRITE_ROUTES)
def test_no_token_on_write_routes_returns_401_and_never_calls_repository(
    monkeypatch, method: str, path: str, body: dict | None, repo_method: str
) -> None:
    # 3.1 -- no token MUST reject with 401 before the DB-pool guard or the
    # repository is ever touched, for every write route.
    calls: list[None] = []
    monkeypatch.setattr(
        PostgresProductRepository,
        repo_method,
        lambda self, *args, **kwargs: calls.append(None),
    )

    with TestClient(app) as client:
        response = client.request(method, path, json=body)

    assert response.status_code == 401
    assert calls == []


@pytest.mark.parametrize(("method", "path", "body", "repo_method"), _WRITE_ROUTES)
def test_valid_token_with_no_pool_returns_503_on_write_routes(
    monkeypatch, method: str, path: str, body: dict | None, repo_method: str
) -> None:
    # 3.2 -- a valid token but an unavailable DB pool MUST reject with 503
    # before the repository is ever touched, for every write route.
    monkeypatch.delenv("DB_URL", raising=False)
    calls: list[None] = []
    monkeypatch.setattr(
        PostgresProductRepository,
        repo_method,
        lambda self, *args, **kwargs: calls.append(None),
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        response = client.request(
            method, path, json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 503
    assert calls == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("POST", "/admin/products", id="post"),
        pytest.param("PATCH", f"/admin/products/{uuid4()}", id="patch"),
    ],
)
def test_slug_in_write_body_is_rejected_with_422(
    monkeypatch, method: str, path: str
) -> None:
    # 3.3 -- `extra="forbid"` on `AdminProductWriteRequest` proves a
    # client-supplied `slug` is REJECTED, never silently dropped.
    calls: list[None] = []
    monkeypatch.setattr(
        PostgresProductRepository,
        "add",
        lambda self, *args, **kwargs: calls.append(None),
    )
    monkeypatch.setattr(
        PostgresProductRepository,
        "update",
        lambda self, *args, **kwargs: calls.append(None),
    )
    token = make_valid_admin_token()
    body = {"name": "Test Product", "model": "TP-1", "variants": [], "slug": "hacked"}

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.request(
            method, path, json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 422
    assert calls == []


def test_valid_post_creates_product_with_server_generated_slug(monkeypatch) -> None:
    # 3.4 -- the response's `slug` is server-derived; the client never sends
    # (and cannot send, per 3.3) one.
    added: list[Product] = []

    async def fake_slug_exists(self, slug: str) -> bool:
        return False

    async def fake_add(self, product: Product) -> None:
        added.append(product)

    monkeypatch.setattr(PostgresProductRepository, "slug_exists", fake_slug_exists)
    monkeypatch.setattr(PostgresProductRepository, "add", fake_add)
    token = make_valid_admin_token()
    body = {"name": "Funda iPhone 15", "model": "IP15", "variants": []}

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["slug"] == "funda-iphone-15"
    assert "slug" not in body
    assert len(added) == 1
    assert added[0].slug == "funda-iphone-15"


def test_post_with_unslugifiable_name_returns_422_not_500(monkeypatch) -> None:
    # Gap found during PR3 review: UnslugifiableProductNameError and
    # SlugGenerationExhaustedError are plain Exception subclasses, not
    # ValueError/TypeError, so design.md's original mapping table left
    # them uncaught -- a name with no alphanumeric content would escape
    # _execute_or_raise as an unhandled 500. Fixed by adding both to the
    # 422 branch explicitly.
    added: list[Product] = []

    async def fake_add(self, product: Product) -> None:
        added.append(product)

    monkeypatch.setattr(PostgresProductRepository, "add", fake_add)
    token = make_valid_admin_token()
    body = {"name": "🎁🎁🎁", "model": "TP-1", "variants": []}

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 422
    assert added == []


def test_get_single_admin_product_returns_200(monkeypatch) -> None:
    # Added post-PR3: GET /admin/products/{id} was in design.md's File
    # Changes table but missed from tasks.md's Phase 3 breakdown -- PR4's
    # edit page needs a single-product fetch, not list-and-filter.
    product = Product(
        id=uuid4(), slug="test-product", name="Test Product", model="TP-1",
        variants=[],
    )

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(product.id)
    assert response.json()["slug"] == "test-product"


def test_get_single_admin_product_unknown_or_retired_returns_404(monkeypatch) -> None:
    async def fake_get_by_id(self, product_id):
        return None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_patch_unknown_or_retired_product_returns_404(monkeypatch) -> None:
    # 3.5 -- PATCH on an unknown/retired id -- `UpdateProductUseCase` raises
    # `ProductNotFoundError` from its own `get_by_id` pre-check.
    async def fake_get_by_id(self, product_id):
        return None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    token = make_valid_admin_token()
    product_id = uuid4()
    body = {"name": "Test Product", "model": "TP-1", "variants": []}

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.patch(
            f"/admin/products/{product_id}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_delete_product_unknown_or_retired_returns_404(monkeypatch) -> None:
    # 3.5 -- DELETE product on an unknown/retired id.
    async def fake_soft_delete(self, product_id):
        raise ProductNotFoundError(product_id)

    monkeypatch.setattr(PostgresProductRepository, "soft_delete", fake_soft_delete)
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.delete(
            f"/admin/products/{product_id}", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_delete_variant_unknown_or_retired_returns_404(monkeypatch) -> None:
    # 3.5 -- DELETE variant on an unknown/retired id.
    async def fake_soft_delete_variant(self, product_id, variant_id):
        raise VariantNotFoundError(variant_id, product_id)

    monkeypatch.setattr(
        PostgresProductRepository, "soft_delete_variant", fake_soft_delete_variant
    )
    token = make_valid_admin_token()
    product_id, variant_id = uuid4(), uuid4()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.delete(
            f"/admin/products/{product_id}/variants/{variant_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_post_with_description_fields_persists_and_echoes_both(monkeypatch) -> None:
    # content-ai-domains PR2, task 2.7 -- both text fields round-trip
    # through the admin API create route (admin-product-management spec
    # "Product is created with only manually typed copy").
    async def fake_slug_exists(self, slug: str) -> bool:
        return False

    added: list[Product] = []

    async def fake_add(self, product: Product) -> None:
        added.append(product)

    monkeypatch.setattr(PostgresProductRepository, "slug_exists", fake_slug_exists)
    monkeypatch.setattr(PostgresProductRepository, "add", fake_add)
    token = make_valid_admin_token()
    body = {
        "name": "Funda con copy",
        "model": "TP-1",
        "variants": [],
        "description": "Descripcion larga escrita a mano",
        "short_description": "Blurb corto",
    }

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["description"] == "Descripcion larga escrita a mano"
    assert payload["short_description"] == "Blurb corto"
    assert len(added) == 1
    assert added[0].description == "Descripcion larga escrita a mano"
    assert added[0].short_description == "Blurb corto"


def test_post_omitting_description_fields_leaves_both_null(monkeypatch) -> None:
    # admin-product-management spec "Product is creatable with both fields
    # blank" -- omitting the two keys entirely, not just sending blanks.
    async def fake_slug_exists(self, slug: str) -> bool:
        return False

    added: list[Product] = []

    async def fake_add(self, product: Product) -> None:
        added.append(product)

    monkeypatch.setattr(PostgresProductRepository, "slug_exists", fake_slug_exists)
    monkeypatch.setattr(PostgresProductRepository, "add", fake_add)
    token = make_valid_admin_token()
    body = {"name": "Funda sin copy", "model": "TP-1", "variants": []}

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["description"] is None
    assert payload["short_description"] is None
    assert added[0].description is None
    assert added[0].short_description is None


def test_patch_updates_description_fields_independently(monkeypatch) -> None:
    # admin-product-management spec "Editing updates both fields
    # independently" -- PATCH persists description/short_description as
    # full-replacement scalars, exactly like name/model.
    product = Product(
        id=uuid4(),
        slug="test-product",
        name="Test Product",
        model="TP-1",
        variants=[],
        description="Descripcion original",
        short_description=None,
    )

    async def fake_get_by_id(self, product_id):
        return product if product_id == product.id else None

    updated: list[Product] = []

    async def fake_update(self, edited: Product) -> None:
        updated.append(edited)

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresProductRepository, "update", fake_update)
    token = make_valid_admin_token()
    body = {
        "name": product.name,
        "model": product.model,
        "variants": [],
        "description": product.description,
        "short_description": "Blurb agregado",
    }

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.patch(
            f"/admin/products/{product.id}",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["short_description"] == "Blurb agregado"
    assert payload["description"] == "Descripcion original"
    assert updated[0].short_description == "Blurb agregado"
    assert updated[0].description == "Descripcion original"


def test_post_over_cap_short_description_returns_422(monkeypatch) -> None:
    # DD4 "over-cap save" -- 422 via Pydantic Field(max_length=160), never a
    # silent truncation.
    token = make_valid_admin_token()
    body = {
        "name": "Test Product",
        "model": "TP-1",
        "variants": [],
        "short_description": "x" * 161,
    }

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            "/admin/products", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 422


async def test_delete_variant_cross_parent_returns_404_not_403(db_pool) -> None:
    # 3.6 -- the highest-value test in this PR (design.md's threat matrix
    # #1, "IDOR across parents"). A spy CANNOT prove this: the whole point
    # is that `PostgresProductRepository.soft_delete_variant`'s real SQL
    # (`WHERE id = $1 AND product_id = $2`) is what rejects the cross-parent
    # id -- so this needs two REAL, persisted products created through the
    # real `CreateProductUseCase`, then a real route call that must NEVER
    # confirm product B's variant exists by returning anything other than a
    # generic 404.
    #
    # Uses `db_pool` (not `db_conn`): the request runs through `TestClient`,
    # which drives its OWN event loop in a background thread via its ASGI
    # lifespan -- an `asyncpg.Connection` created on pytest's event loop
    # (as `db_conn`'s held-open transaction is) cannot be reused there.
    # `db_pool`-acquired connections are used and released, never held
    # across the loop boundary; the two products are committed for real and
    # explicitly cleaned up in `finally`.
    async with db_pool.acquire() as conn:
        repository = PostgresProductRepository(conn)
        product_a = await CreateProductUseCase(repository=repository).execute(
            name=f"IDOR Product A {uuid4()}", model="Model A", variants=[]
        )
        product_b = await CreateProductUseCase(repository=repository).execute(
            name=f"IDOR Product B {uuid4()}",
            model="Model B",
            variants=[
                ProductVariant(
                    id=uuid4(), color="Red", price=Decimal("10.00"), cost=Decimal("5.00")
                )
            ],
        )
    variant_b_id = product_b.variants[0].id
    token = make_valid_admin_token()

    try:
        with TestClient(app) as client:
            response = client.delete(
                f"/admin/products/{product_a.id}/variants/{variant_b_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "not_found"}

        async with db_pool.acquire() as conn:
            still_active = await PostgresProductRepository(conn).get_by_id(product_b.id)
        assert still_active is not None
        assert any(variant.id == variant_b_id for variant in still_active.variants)
    finally:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM products WHERE id = ANY($1::uuid[])",
                [product_a.id, product_b.id],
            )
