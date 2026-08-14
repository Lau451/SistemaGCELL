"""Object storage port for product image bytes.

Cross-domain capability port (design.md Decision 1) -- lives in
`shared/application/`, NOT `products/application/`, so its
`shared/infrastructure/` adapter (`supabase_storage.py`) never needs to
import from `products/` -- the wrong dependency direction; see
`shared/infrastructure/postgres.py`'s module docstring, which states the
same rule for the DB transaction seam ("`shared/` must never import from
`products/` or `stock/`"). Zero framework imports here, same rule as
`products/application/` ports (`image_repository.py`).
"""

from typing import Protocol


class ObjectStorage(Protocol):
    """Port implemented by infrastructure adapters (Supabase Storage over
    httpx -- see `shared/infrastructure/supabase_storage.py`).
    """

    async def put(self, path: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, path: str) -> None:
        """MUST be IDEMPOTENT -- a missing object is success, never an
        error (see design.md Decision 5: "DELETE ORDER"). Adapters raise
        `ObjectStorageError` only for a genuine, non-404 failure.
        """
        ...


class ObjectStorageError(Exception):
    """Raised by an `ObjectStorage` adapter on a non-idempotent failure
    (a `put` failure, or a `delete` failure for a reason other than the
    object already being absent). Maps to `502` at the route layer (see
    design.md "Status mapping": "NEW 502 ObjectStorageError").
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
