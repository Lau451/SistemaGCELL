"""Integration tests for the `/admin` copy/alt-text GENERATE routes (PR 11).

Mirrors `test_admin_images.py`'s exact conventions: `TestClient`, a forged
admin JWT (`admin_jwt_integration_support`), and monkeypatched-spy
adapters -- never a live Postgres, Supabase Storage, or Gemini call.

Proves design.md's dependency order (401 -> `require_db_pool` 503 ->
`require_storage` 503 [alt-text route only] -> `require_gemini` 503,
Threat-Matrix "Routing" row), the "zero write side effect" rule (D5,
admin-ai-content-authoring spec "Generate Calls Have Zero Write Side
Effect" -- asserted before/after the request, not just "some assertion
somewhere"), the IDOR guard on the alt-text route (Threat-Matrix "IDOR"
row, mirrors 5.1/5.5's cross-parent-returns-same-body-as-unknown-id
convention), and that neither route accepts more than one product/image
id per request (spec "No bulk generate route exists").
"""

from collections.abc import Callable
from decimal import Decimal
from uuid import uuid4

import pytest
from admin_jwt_integration_support import make_valid_admin_token
from fastapi.testclient import TestClient

from gcell.ai.application.content_generator import GenerationError, GenerationRefusedError
from gcell.ai.infrastructure.gemini_content_generator import GeminiContentGenerator
from gcell.main import app
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.domain.product_image import ProductImage
from gcell.products.infrastructure.postgres_product_image_repository import (
    PostgresProductImageRepository,
)
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.shared.infrastructure.supabase_storage import SupabaseStorage


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


def _spy(calls: list[str], label: str) -> Callable:
    async def _fn(self, *args, **kwargs):
        calls.append(label)

    return _fn


def _spy_all_write_adapters(monkeypatch, calls: list[str]) -> None:
    """Spy on every WRITE method reachable from either generate route's
    dependency graph -- products, images, AND Storage. "Zero write side
    effect" (D5) means none of these must EVER be called, on any of the
    guard-rejection paths OR the success path.
    """
    for name in ("add", "update", "soft_delete", "soft_delete_variant"):
        monkeypatch.setattr(
            PostgresProductRepository, name, _spy(calls, f"product_repo.{name}"), raising=False
        )
    for name in ("add", "delete", "reorder", "update_alt_text"):
        monkeypatch.setattr(
            PostgresProductImageRepository,
            name,
            _spy(calls, f"image_repo.{name}"),
            raising=False,
        )
    monkeypatch.setattr(SupabaseStorage, "put", _spy(calls, "storage.put"), raising=False)
    monkeypatch.setattr(SupabaseStorage, "delete", _spy(calls, "storage.delete"), raising=False)


def _spy_gemini(monkeypatch, calls: list[str]) -> None:
    async def _fn(self, **kwargs):
        calls.append("gemini.generate_json")
        return {}

    monkeypatch.setattr(GeminiContentGenerator, "generate_json", _fn)


_GENERATE_SUFFIXES = [
    pytest.param("/copy/generate", id="generate-copy"),
    pytest.param(f"/images/{uuid4()}/alt-text/generate", id="generate-alt-text"),
]


@pytest.mark.parametrize("suffix", _GENERATE_SUFFIXES)
def test_no_token_on_generate_routes_returns_401_and_never_calls_anything(
    monkeypatch, suffix: str
) -> None:
    calls: list[str] = []
    _spy_all_write_adapters(monkeypatch, calls)
    _spy_gemini(monkeypatch, calls)
    product_id = uuid4()

    with TestClient(app) as client:
        response = client.post(f"/admin/products/{product_id}{suffix}")

    assert response.status_code == 401
    assert calls == []


@pytest.mark.parametrize("suffix", _GENERATE_SUFFIXES)
def test_valid_token_with_no_pool_returns_503_on_generate_routes(
    monkeypatch, suffix: str
) -> None:
    monkeypatch.delenv("DB_URL", raising=False)
    calls: list[str] = []
    _spy_all_write_adapters(monkeypatch, calls)
    _spy_gemini(monkeypatch, calls)
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        response = client.post(
            f"/admin/products/{product_id}{suffix}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 503
    assert calls == []


@pytest.mark.parametrize("suffix", _GENERATE_SUFFIXES)
def test_valid_token_with_pool_but_no_gemini_key_returns_503_and_no_gemini_call(
    monkeypatch, suffix: str
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # The alt-text route also depends on `require_storage`, ordered BEFORE
    # `require_gemini` (design.md DD4) -- Storage is configured here so
    # this test's 503 is attributable to the missing Gemini key
    # specifically, not to `require_storage` firing first.
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    calls: list[str] = []
    _spy_all_write_adapters(monkeypatch, calls)
    _spy_gemini(monkeypatch, calls)
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product_id}{suffix}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "gemini_unavailable"}
    assert calls == []


def test_valid_token_with_pool_but_no_storage_config_returns_503_on_alt_text_route(
    monkeypatch,
) -> None:
    # `copy/generate` has no `require_storage` dependency at all (only the
    # alt-text route needs three guards, design.md DD4) -- this case is
    # deliberately alt-text-only, mirroring `test_admin_images.py`'s
    # `test_valid_token_with_pool_but_no_storage_config_returns_503`.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    calls: list[str] = []
    _spy_all_write_adapters(monkeypatch, calls)
    _spy_gemini(monkeypatch, calls)
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product_id}/images/{uuid4()}/alt-text/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 503
    assert calls == []


def test_generate_copy_returns_200_with_zero_db_row_changes(monkeypatch) -> None:
    product_id = uuid4()
    product = Product(
        id=product_id,
        slug="funda-iphone-16",
        name="Funda iPhone 16",
        model="iPhone 16",
        variants=[
            ProductVariant(
                id=uuid4(), color="negro", price=Decimal("5000.00"), cost=Decimal("2000.00")
            )
        ],
    )
    calls: list[str] = []
    _spy_all_write_adapters(monkeypatch, calls)

    async def fake_get_by_id(self, pid):
        return product if pid == product_id else None

    async def fake_generate_json(self, **kwargs):
        calls.append("gemini.generate_json")
        return {
            "short_description": "Funda resistente",
            "description": "Una funda de alta calidad para tu telefono.",
        }

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(GeminiContentGenerator, "generate_json", fake_generate_json)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    token = make_valid_admin_token()

    before = list(calls)
    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product_id}/copy/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
    after = list(calls)

    assert response.status_code == 200
    assert response.json() == {
        "short_description": "Funda resistente",
        "description": "Una funda de alta calidad para tu telefono.",
    }
    # Zero write side effect (D5): the only call recorded across the whole
    # request is the read-only Gemini generation itself -- no repository
    # or Storage WRITE method fired, asserted before AND after the request
    # (spec "Generating copy does not persist anything").
    assert before == []
    assert after == ["gemini.generate_json"]


@pytest.mark.parametrize(
    ("exception", "expected_detail"),
    [
        pytest.param(GenerationError("transport failure"), "generation_failed", id="failed"),
        pytest.param(
            GenerationRefusedError("safety block"), "generation_refused", id="refused"
        ),
    ],
)
def test_generate_copy_gemini_failure_maps_to_502_never_a_200_with_an_empty_draft(
    monkeypatch, exception: Exception, expected_detail: str
) -> None:
    # spec (gemini-generation) "Gemini call failure surfaces as an error":
    # a failed/refused Gemini call MUST be a distinct error response, never
    # `200` with an empty draft. `GenerationRefusedError` (a subclass) must
    # map to a DIFFERENT `detail` than the plain `GenerationError` case
    # (design.md DD4).
    product_id = uuid4()
    product = Product(id=product_id, slug="funda", name="Funda", model="F-1")

    async def fake_get_by_id(self, pid):
        return product if pid == product_id else None

    async def fake_generate_json(self, **kwargs):
        raise exception

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(GeminiContentGenerator, "generate_json", fake_generate_json)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product_id}/copy/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 502
    assert response.json() == {"detail": expected_detail}


def test_generate_alt_text_cross_parent_image_id_returns_404_same_body_as_unknown_id(
    monkeypatch,
) -> None:
    product_a_id = uuid4()
    product_b_id = uuid4()
    product_a = Product(id=product_a_id, slug="product-a", name="Product A", model="A-1")
    image_of_b = ProductImage(
        id=uuid4(),
        product_id=product_b_id,
        variant_id=None,
        storage_path="product-b/hero-abc123456789.webp",
        alt_text=None,
        sort_order=0,
    )
    calls: list[str] = []
    _spy_all_write_adapters(monkeypatch, calls)
    _spy_gemini(monkeypatch, calls)

    async def fake_get_by_id(self, pid):
        return product_a if pid == product_a_id else None

    async def fake_list_for_product(self, pid):
        # `image_of_b` never appears under product A's own image list --
        # DD2's ownership-via-query-scope: a cross-parent id structurally
        # cannot resolve here.
        return []

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresProductImageRepository, "list_for_product", fake_list_for_product
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        cross_parent_response = client.post(
            f"/admin/products/{product_a_id}/images/{image_of_b.id}/alt-text/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
        unknown_id_response = client.post(
            f"/admin/products/{product_a_id}/images/{uuid4()}/alt-text/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert cross_parent_response.status_code == 404
    assert unknown_id_response.status_code == 404
    assert (
        cross_parent_response.json()
        == unknown_id_response.json()
        == {"detail": "not_found"}
    )
    # Never reached Storage or Gemini -- the IDOR/unknown-id guard fires
    # inside `photo_context`, before `ObjectStorage.get` or
    # `ContentGenerator.generate_json` is ever called.
    assert calls == []


def test_generate_routes_accept_exactly_one_product_or_image_id_per_request() -> None:
    # Structural proof (spec "No bulk generate route exists"): neither
    # route declares a request body, and every PATH parameter is a scalar
    # (never an array) -- so there is no way to submit more than one
    # product/image id in a single request.
    schema = app.openapi()
    copy_path = "/admin/products/{product_id}/copy/generate"
    alt_text_path = "/admin/products/{product_id}/images/{image_id}/alt-text/generate"
    assert copy_path in schema["paths"]
    assert alt_text_path in schema["paths"]

    for path in (copy_path, alt_text_path):
        operation = schema["paths"][path]["post"]
        assert "requestBody" not in operation
        for param in operation.get("parameters", []):
            if param["in"] == "path":
                assert param["schema"].get("type") != "array"
