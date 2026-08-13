"""Errors raised by the products application layer.

Kept here (not in `domain/`) because these are persistence-outcome errors —
they describe how the repository port reacts to a write conflict or a
missing/retired target, not a domain invariant. Adapters (in-memory,
Postgres) translate their own constraint-violation/zero-rows-affected shape
into these same exception types so use cases stay adapter-agnostic.
"""

from uuid import UUID


class DuplicateProductSlugError(Exception):
    """Raised when registering a product whose `slug` is already taken.

    `slug` is the only DB-unique business identifier for a product (see
    `product-persistence` spec) — this mirrors the `products_slug_key`
    unique constraint.
    """

    def __init__(self, slug: str) -> None:
        super().__init__(f"Product with slug '{slug}' is already registered")
        self.slug = slug


class ProductNotFoundError(Exception):
    """Raised when an operation targets a product id that has no ACTIVE
    (non-retired) product — either the id never existed or the product was
    already soft-deleted. `update` and `soft_delete` both raise this on
    zero rows affected (see design.md "Port additions").
    """

    def __init__(self, product_id: UUID) -> None:
        super().__init__(f"No active product with id '{product_id}'")
        self.product_id = product_id


class VariantNotFoundError(Exception):
    """Raised when an operation targets a variant that does not belong to
    the given product — the variant id does not exist, belongs to a
    different product (IDOR guard, never a 403 that confirms existence
    across a wrong parent), or is already retired.
    """

    def __init__(self, variant_id: UUID, product_id: UUID) -> None:
        super().__init__(
            f"No active variant '{variant_id}' for product '{product_id}'"
        )
        self.variant_id = variant_id
        self.product_id = product_id


class UnslugifiableProductNameError(Exception):
    """Raised when a product name has no alphanumeric content and no slug
    can be derived from it. `slugify` never fabricates a placeholder slug
    (e.g. `product-1`) — that would hide a data-entry error behind a
    meaningless permanent URL.
    """

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Cannot derive a slug from name '{name}': no alphanumeric content"
        )
        self.name = name


class ImageNotFoundError(Exception):
    """Raised when an operation targets an image id that does not belong
    to the given product — unknown id, belongs to a different product
    (IDOR guard, never a 403 that confirms existence across a wrong
    parent — see admin-product-images spec "Image Ownership Is Checked At
    The Use-Case Layer"), or already deleted.
    """

    def __init__(self, image_id: UUID, product_id: UUID) -> None:
        super().__init__(f"No image '{image_id}' for product '{product_id}'")
        self.image_id = image_id
        self.product_id = product_id


class UnsupportedImageError(Exception):
    """Raised when an uploaded file fails mime-type/format/decode
    validation before any Storage write is attempted (see
    product-media-storage spec "Upload Validation Runs Before Any Storage
    Write" and the Pillow guardrail table in design.md).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Unsupported image: {reason}")
        self.reason = reason


class ImageTooLargeError(Exception):
    """Raised when an uploaded file exceeds `MAX_UPLOAD_BYTES` before any
    Storage write is attempted (see admin-product-images spec "Upload
    Validation Runs Before Any Storage Write").
    """

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        super().__init__(
            f"Image size {size_bytes} bytes exceeds the {max_bytes}-byte limit"
        )
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
