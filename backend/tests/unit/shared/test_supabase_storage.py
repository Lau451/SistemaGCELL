"""Unit tests for the httpx-backed `SupabaseStorage` adapter.

No live network/Storage call -- `httpx.MockTransport` fakes the transport
layer entirely (see the PR prompt: "unit-tested with a mocked/faked
transport, not against the real bucket"; the real bucket is exercised
later in PR5's integration tests and the final manual E2E).
"""

import httpx
import pytest

from gcell.shared.application.object_storage import ObjectStorageError
from gcell.shared.infrastructure.supabase_storage import SupabaseStorage


def _storage(handler) -> SupabaseStorage:
    return SupabaseStorage(
        url="http://127.0.0.1:54321",
        service_role_key="service-role-key",
        bucket="product-photos",
        transport=httpx.MockTransport(handler),
    )


class TestPut:
    async def test_sends_bytes_to_the_expected_object_path_with_auth_headers(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            captured["content"] = request.content
            return httpx.Response(200, json={"Key": "product-photos/hero-abc123.webp"})

        storage = _storage(handler)

        await storage.put("hero-abc123.webp", b"webp-bytes-here", "image/webp")

        assert captured["method"] == "POST"
        assert "/object/product-photos/hero-abc123.webp" in captured["url"]
        assert captured["headers"]["authorization"] == "Bearer service-role-key"
        assert captured["headers"]["apikey"] == "service-role-key"
        assert captured["headers"]["content-type"] == "image/webp"
        assert captured["content"] == b"webp-bytes-here"

    async def test_raises_object_storage_error_on_failure_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"message": "internal error"})

        storage = _storage(handler)

        with pytest.raises(ObjectStorageError):
            await storage.put("hero-abc123.webp", b"data", "image/webp")

    async def test_succeeds_on_2xx_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"Key": "ok"})

        storage = _storage(handler)

        await storage.put("hero-abc123.webp", b"data", "image/webp")  # no raise


class TestDelete:
    async def test_sends_delete_to_the_expected_object_path_with_auth_headers(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            return httpx.Response(200, json={"message": "Successfully deleted"})

        storage = _storage(handler)

        await storage.delete("hero-abc123.webp")

        assert captured["method"] == "DELETE"
        assert "/object/product-photos/hero-abc123.webp" in captured["url"]
        assert captured["headers"]["authorization"] == "Bearer service-role-key"
        assert captured["headers"]["apikey"] == "service-role-key"

    async def test_is_idempotent_when_the_object_is_already_missing(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "not found"})

        storage = _storage(handler)

        await storage.delete("already-gone.webp")  # no raise -- 404 is success

    async def test_raises_object_storage_error_on_a_non_404_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"message": "internal error"})

        storage = _storage(handler)

        with pytest.raises(ObjectStorageError):
            await storage.delete("hero-abc123.webp")
