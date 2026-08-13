"""Product images domain model.

Pure Python only — zero framework imports (no FastAPI, no Pydantic, no
DB/Supabase client, no SQLAlchemy, no httpx). Mirrors `product.py`: images
are their own aggregate (see design.md Decision 1), not a `Product` field.
"""

from dataclasses import dataclass
from uuid import UUID

# 5 MiB — mirrors the `product-photos` bucket's size ceiling (see
# product-media-storage spec "Upload Validation Runs Before Any Storage
# Write").
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Bucket-legal mime types. Classification of the decoded bytes (not the
# client-supplied `content_type` header) happens in the normalizer adapter
# (Phase 3) — this allowlist is what an upload is checked against.
ALLOWED_UPLOAD_MIMES = {"image/jpeg", "image/png", "image/webp"}


@dataclass(eq=False)
class ProductImage:
    """A single image attached to a product, optionally scoped to a variant.

    Invariants:
    - `storage_path` cannot be blank.
    - `sort_order` must be non-negative.
    - `variant_id = None` means a product hero image (see admin-product-images
      spec "Hero Assignment Uses A Null Variant Id") — this is not an error
      state.

    Equality and hashing are based on `id` alone (not field values) — same
    convention as `Product`/`ProductVariant`.
    """

    id: UUID
    product_id: UUID
    variant_id: UUID | None
    storage_path: str
    alt_text: str | None
    sort_order: int

    def __post_init__(self) -> None:
        if not self.storage_path or not self.storage_path.strip():
            raise ValueError("ProductImage.storage_path cannot be blank")
        if self.sort_order < 0:
            raise ValueError("ProductImage.sort_order cannot be negative")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProductImage):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
