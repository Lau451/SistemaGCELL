"""Integration tests for the `/admin` product-images routes.

Mirrors `test_admin.py`'s conventions: `TestClient`, `admin_jwt_integration_
support`'s forged token, and monkeypatched-spy adapters -- never a live
Supabase Storage or live Postgres.

Proves design.md's dependency order (401 -> `require_db_pool` 503 ->
`require_storage` 503) and that `require_storage` is deliberately a
dependency ONLY on the two routes whose use case actually touches
`ObjectStorage` (upload, delete) -- GET and the reorder PUT never call
Storage (admin-product-images spec "Reorder Updates Sort Order ... no
Storage touch"), so a missing Supabase Storage config must never block
listing or reordering. Also proves the IDOR guard (404, never 403, on a
cross-product image id) and that upload validation runs BEFORE any Storage
write (a rejected file must never reach `SupabaseStorage.put`).
"""

from collections.abc import Callable
from io import BytesIO
from uuid import uuid4

import pytest
from admin_jwt_integration_support import make_valid_admin_token
from fastapi.testclient import TestClient
from PIL import Image

from gcell.main import app
from gcell.products.domain.product import Product
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


def _valid_png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (4, 4), color="red").save(buf, format="PNG")
    return buf.getvalue()


def _spy(calls: list[str], label: str) -> Callable:
    async def _fn(self, *args, **kwargs):
        calls.append(label)

    return _fn


def _spy_all_adapters(monkeypatch, calls: list[str]) -> None:
    for name in (
        "add",
        "get_by_id",
        "list_for_product",
        "delete",
        "next_sort_order",
        "reorder",
        "update_alt_text",
    ):
        monkeypatch.setattr(
            PostgresProductImageRepository, name, _spy(calls, f"image_repo.{name}"), raising=False
        )
    monkeypatch.setattr(
        PostgresProductRepository, "get_by_id", _spy(calls, "product_repo.get_by_id")
    )
    monkeypatch.setattr(SupabaseStorage, "put", _spy(calls, "storage.put"))
    monkeypatch.setattr(SupabaseStorage, "delete", _spy(calls, "storage.delete"))


def _request_kwargs(kind: str | None):
    if kind == "multipart":
        return {"files": {"file": ("test.png", _valid_png_bytes(), "image/png")}}
    if kind == "json":
        return {"json": {"image_ids": []}}
    if kind == "alt-text-json":
        return {"json": {"alt_text": "A red case"}}
    return {}


_IMAGE_ROUTES = [
    pytest.param("GET", "/images", None, id="list-images"),
    pytest.param("POST", "/images", "multipart", id="upload-image"),
    pytest.param("DELETE", f"/images/{uuid4()}", None, id="delete-image"),
    pytest.param("PUT", "/images/order", "json", id="reorder-images"),
    pytest.param(
        "PATCH", f"/images/{uuid4()}", "alt-text-json", id="update-alt-text"
    ),
]

_STORAGE_TOUCHING_ROUTES = [
    pytest.param("POST", "/images", "multipart", id="upload-image"),
    pytest.param("DELETE", f"/images/{uuid4()}", None, id="delete-image"),
]


@pytest.mark.parametrize(("method", "suffix", "kind"), _IMAGE_ROUTES)
def test_no_token_on_image_routes_returns_401_and_never_calls_repository_or_storage(
    monkeypatch, method: str, suffix: str, kind: str | None
) -> None:
    calls: list[str] = []
    _spy_all_adapters(monkeypatch, calls)
    product_id = uuid4()

    with TestClient(app) as client:
        response = client.request(
            method, f"/admin/products/{product_id}{suffix}", **_request_kwargs(kind)
        )

    assert response.status_code == 401
    assert calls == []


@pytest.mark.parametrize(("method", "suffix", "kind"), _IMAGE_ROUTES)
def test_valid_token_with_no_pool_returns_503_on_image_routes(
    monkeypatch, method: str, suffix: str, kind: str | None
) -> None:
    monkeypatch.delenv("DB_URL", raising=False)
    calls: list[str] = []
    _spy_all_adapters(monkeypatch, calls)
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        response = client.request(
            method,
            f"/admin/products/{product_id}{suffix}",
            headers={"Authorization": f"Bearer {token}"},
            **_request_kwargs(kind),
        )

    assert response.status_code == 503
    assert calls == []


@pytest.mark.parametrize(("method", "suffix", "kind"), _STORAGE_TOUCHING_ROUTES)
def test_valid_token_with_pool_but_no_storage_config_returns_503(
    monkeypatch, method: str, suffix: str, kind: str | None
) -> None:
    # GET and PUT .../order are deliberately excluded from
    # `_STORAGE_TOUCHING_ROUTES` -- neither use case touches `ObjectStorage`
    # (see module docstring), so a missing Storage config must never block
    # them; only upload and delete depend on `require_storage`.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    calls: list[str] = []
    _spy_all_adapters(monkeypatch, calls)
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.request(
            method,
            f"/admin/products/{product_id}{suffix}",
            headers={"Authorization": f"Bearer {token}"},
            **_request_kwargs(kind),
        )

    assert response.status_code == 503
    assert calls == []


def test_get_admin_product_images_returns_200_with_list(monkeypatch) -> None:
    product_id = uuid4()
    image = ProductImage(
        id=uuid4(),
        product_id=product_id,
        variant_id=None,
        storage_path="test-product/hero-abc123456789.webp",
        alt_text="A hero shot",
        sort_order=0,
    )

    async def fake_list_for_product(self, pid):
        return [image] if pid == product_id else []

    monkeypatch.setattr(
        PostgresProductImageRepository, "list_for_product", fake_list_for_product
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.get(
            f"/admin/products/{product_id}/images",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "id": str(image.id),
            "product_id": str(product_id),
            "variant_id": None,
            "storage_path": "test-product/hero-abc123456789.webp",
            "alt_text": "A hero shot",
            "sort_order": 0,
        }
    ]


def test_upload_admin_product_image_with_valid_image_returns_201(monkeypatch) -> None:
    product_id = uuid4()
    product = Product(id=product_id, slug="test-product", name="Test Product", model="TP-1")
    added: list[ProductImage] = []
    put_calls: list[tuple[str, bytes, str]] = []

    async def fake_get_by_id(self, pid):
        return product if pid == product_id else None

    async def fake_next_sort_order(self, pid, vid):
        return 0

    async def fake_add(self, image):
        added.append(image)

    async def fake_put(self, path, data, content_type):
        put_calls.append((path, data, content_type))

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresProductImageRepository, "next_sort_order", fake_next_sort_order)
    monkeypatch.setattr(PostgresProductImageRepository, "add", fake_add)
    monkeypatch.setattr(SupabaseStorage, "put", fake_put)
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product_id}/images",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.png", _valid_png_bytes(), "image/png")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["product_id"] == str(product_id)
    assert body["variant_id"] is None
    assert body["sort_order"] == 0
    assert body["storage_path"].startswith("test-product/hero-")
    assert body["storage_path"].endswith(".webp")
    assert len(added) == 1
    assert added[0].storage_path == body["storage_path"]
    # Normalizer always re-encodes to WebP (design.md Decision 3) -- proves
    # the route ran the real `PillowImageNormalizer`, not a stub.
    assert len(put_calls) == 1
    assert put_calls[0][2] == "image/webp"


def test_upload_admin_product_image_unsupported_file_returns_422_before_any_storage_write(
    monkeypatch,
) -> None:
    product_id = uuid4()
    product = Product(id=product_id, slug="test-product", name="Test Product", model="TP-1")
    calls: list[str] = []

    async def fake_get_by_id(self, pid):
        return product if pid == product_id else None

    monkeypatch.setattr(PostgresProductRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresProductImageRepository, "add", _spy(calls, "image_repo.add"))
    monkeypatch.setattr(SupabaseStorage, "put", _spy(calls, "storage.put"))
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.post(
            f"/admin/products/{product_id}/images",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.txt", b"not an image, just plain text bytes", "text/plain")},
        )

    assert response.status_code == 422
    assert calls == []


def test_delete_admin_product_image_returns_204(monkeypatch) -> None:
    product_id = uuid4()
    image = ProductImage(
        id=uuid4(),
        product_id=product_id,
        variant_id=None,
        storage_path="test-product/hero-abc123456789.webp",
        alt_text=None,
        sort_order=0,
    )
    deleted: list = []
    storage_deleted: list[str] = []

    async def fake_get_by_id(self, image_id):
        return image if image_id == image.id else None

    async def fake_delete(self, image_id):
        deleted.append(image_id)

    async def fake_storage_delete(self, path):
        storage_deleted.append(path)

    monkeypatch.setattr(PostgresProductImageRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(PostgresProductImageRepository, "delete", fake_delete)
    monkeypatch.setattr(SupabaseStorage, "delete", fake_storage_delete)
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.delete(
            f"/admin/products/{product_id}/images/{image.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 204
    assert deleted == [image.id]
    assert storage_deleted == [image.storage_path]


def test_delete_admin_product_image_cross_product_returns_404_not_403(monkeypatch) -> None:
    product_a_id = uuid4()
    product_b_id = uuid4()
    image_of_b = ProductImage(
        id=uuid4(),
        product_id=product_b_id,
        variant_id=None,
        storage_path="product-b/hero-abc123456789.webp",
        alt_text=None,
        sort_order=0,
    )
    calls: list[str] = []

    async def fake_get_by_id(self, image_id):
        return image_of_b if image_id == image_of_b.id else None

    monkeypatch.setattr(PostgresProductImageRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresProductImageRepository, "delete", _spy(calls, "image_repo.delete")
    )
    monkeypatch.setattr(SupabaseStorage, "delete", _spy(calls, "storage.delete"))
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.delete(
            f"/admin/products/{product_a_id}/images/{image_of_b.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}
    assert calls == []


def test_reorder_admin_product_images_returns_200_with_new_order(monkeypatch) -> None:
    product_id = uuid4()
    images = [
        ProductImage(
            id=uuid4(),
            product_id=product_id,
            variant_id=None,
            storage_path=f"test-product/hero-{i}23456789012.webp",
            alt_text=None,
            sort_order=i,
        )
        for i in range(3)
    ]
    reorder_calls: list[tuple] = []
    submitted_order = [images[2].id, images[0].id, images[1].id]

    async def fake_list_for_product(self, pid):
        return images if pid == product_id else []

    async def fake_reorder(self, pid, ordered_image_ids):
        reorder_calls.append((pid, ordered_image_ids))

    monkeypatch.setattr(
        PostgresProductImageRepository, "list_for_product", fake_list_for_product
    )
    monkeypatch.setattr(PostgresProductImageRepository, "reorder", fake_reorder)
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.put(
            f"/admin/products/{product_id}/images/order",
            json={"image_ids": [str(i) for i in submitted_order]},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert len(response.json()) == 3
    assert reorder_calls == [(product_id, submitted_order)]


def test_reorder_admin_product_images_foreign_id_returns_404_and_zero_writes(
    monkeypatch,
) -> None:
    product_id = uuid4()
    own_image = ProductImage(
        id=uuid4(),
        product_id=product_id,
        variant_id=None,
        storage_path="test-product/hero-abc123456789.webp",
        alt_text=None,
        sort_order=0,
    )
    foreign_image_id = uuid4()
    calls: list[str] = []

    async def fake_list_for_product(self, pid):
        return [own_image] if pid == product_id else []

    monkeypatch.setattr(
        PostgresProductImageRepository, "list_for_product", fake_list_for_product
    )
    monkeypatch.setattr(
        PostgresProductImageRepository, "reorder", _spy(calls, "image_repo.reorder")
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.put(
            f"/admin/products/{product_id}/images/order",
            json={"image_ids": [str(own_image.id), str(foreign_image_id)]},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}
    assert calls == []


def test_update_admin_product_image_alt_text_returns_200(monkeypatch) -> None:
    product_id = uuid4()
    image = ProductImage(
        id=uuid4(),
        product_id=product_id,
        variant_id=None,
        storage_path="test-product/hero-abc123456789.webp",
        alt_text="",
        sort_order=0,
    )
    update_calls: list[tuple] = []

    async def fake_get_by_id(self, image_id):
        return image if image_id == image.id else None

    async def fake_update_alt_text(self, image_id, alt_text):
        update_calls.append((image_id, alt_text))

    monkeypatch.setattr(PostgresProductImageRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresProductImageRepository, "update_alt_text", fake_update_alt_text
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.patch(
            f"/admin/products/{product_id}/images/{image.id}",
            json={"alt_text": "A red case"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(image.id)
    assert body["alt_text"] == "A red case"
    assert body["storage_path"] == image.storage_path
    assert body["sort_order"] == image.sort_order
    assert update_calls == [(image.id, "A red case")]


def test_update_admin_product_image_alt_text_cross_product_returns_404_not_403(
    monkeypatch,
) -> None:
    product_a_id = uuid4()
    product_b_id = uuid4()
    image_of_b = ProductImage(
        id=uuid4(),
        product_id=product_b_id,
        variant_id=None,
        storage_path="product-b/hero-abc123456789.webp",
        alt_text="Belongs to B",
        sort_order=0,
    )
    calls: list[str] = []

    async def fake_get_by_id(self, image_id):
        return image_of_b if image_id == image_of_b.id else None

    monkeypatch.setattr(PostgresProductImageRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresProductImageRepository,
        "update_alt_text",
        _spy(calls, "image_repo.update_alt_text"),
    )
    token = make_valid_admin_token()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.patch(
            f"/admin/products/{product_a_id}/images/{image_of_b.id}",
            json={"alt_text": "Hijacked"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}
    assert calls == []


def test_update_admin_product_image_alt_text_unknown_id_returns_404(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_get_by_id(self, image_id):
        return None

    monkeypatch.setattr(PostgresProductImageRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(
        PostgresProductImageRepository,
        "update_alt_text",
        _spy(calls, "image_repo.update_alt_text"),
    )
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.patch(
            f"/admin/products/{product_id}/images/{uuid4()}",
            json={"alt_text": "whatever"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}
    assert calls == []


def test_update_admin_product_image_alt_text_missing_key_returns_422(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        PostgresProductImageRepository,
        "update_alt_text",
        _spy(calls, "image_repo.update_alt_text"),
    )
    monkeypatch.setattr(
        PostgresProductImageRepository, "get_by_id", _spy(calls, "image_repo.get_by_id")
    )
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.patch(
            f"/admin/products/{product_id}/images/{uuid4()}",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    assert calls == []


def test_reorder_extra_field_in_body_returns_422(monkeypatch) -> None:
    # `extra="forbid"` proof, same convention as `AdminProductWriteRequest`
    # (test_admin.py's `test_slug_in_write_body_is_rejected_with_422`).
    calls: list[str] = []
    monkeypatch.setattr(
        PostgresProductImageRepository, "reorder", _spy(calls, "image_repo.reorder")
    )
    token = make_valid_admin_token()
    product_id = uuid4()

    with TestClient(app) as client:
        client.app.state.db_pool = _FakePool()
        response = client.put(
            f"/admin/products/{product_id}/images/order",
            json={"image_ids": [], "sort_order": 1},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    assert calls == []
