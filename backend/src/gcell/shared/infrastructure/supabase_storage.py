"""Thin httpx adapter over the Supabase Storage REST API.

Rejected `supabase-py`/`storage3` (design.md Decision 9) -- it pulls in
gotrue/postgrest/realtime for two HTTP calls; this repo's posture is thin
explicit adapters (hand-rolled Postgres adapter, no ORM), so a
hand-rolled Storage adapter matches. `httpx` is confined to
`shared/infrastructure/` -- never imported from `domain/` (see
`test_domain_boundary.py`'s `BANNED_MODULES`).

Not wired into any use case yet -- that is Phase 4. Unit-tested with
`httpx.MockTransport` (no live network call); the real bucket is
exercised in a later PR's integration tests.
"""

import httpx

from gcell.shared.application.object_storage import (
    ObjectStorage,
    ObjectStorageError,
    StoredObject,
)


class SupabaseStorage(ObjectStorage):
    """The only production `ObjectStorage`. Holds the backend-only
    `service_role` credential (design.md "Backend Service Role Upload
    And Delete Contract") -- never constructed with a value derived from
    a `NEXT_PUBLIC_*` env var.
    """

    def __init__(
        self,
        *,
        url: str,
        service_role_key: str,
        bucket: str = "product-photos",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = httpx.AsyncClient(
            base_url=f"{url.rstrip('/')}/storage/v1",
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "apikey": service_role_key,
            },
            transport=transport,
        )

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        response = await self._client.post(
            f"/object/{self._bucket}/{path}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        if response.status_code >= 400:
            raise ObjectStorageError(
                f"Storage put failed for '{path}': {response.status_code} {response.text}"
            )

    async def get(self, path: str) -> StoredObject:
        response = await self._client.get(f"/object/{self._bucket}/{path}")
        if response.status_code >= 400:
            # NOT idempotent-on-404 like `delete` -- see `ObjectStorage.get`'s
            # docstring and design.md Decision 1.
            raise ObjectStorageError(
                f"Storage get failed for '{path}': {response.status_code} {response.text}"
            )
        return StoredObject(
            data=response.content,
            content_type=response.headers["content-type"],
        )

    async def delete(self, path: str) -> None:
        response = await self._client.delete(f"/object/{self._bucket}/{path}")
        if response.status_code == 404:
            # IDEMPOTENT -- see `ObjectStorage.delete`'s docstring and
            # design.md Decision 5 ("404 = success").
            return
        if response.status_code >= 400:
            raise ObjectStorageError(
                f"Storage delete failed for '{path}': {response.status_code} {response.text}"
            )
