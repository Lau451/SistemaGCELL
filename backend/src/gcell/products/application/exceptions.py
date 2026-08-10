"""Errors raised by the products application layer.

Kept here (not in `domain/`) because these are persistence-outcome errors —
they describe how the repository port reacts to a write conflict, not a
domain invariant. Adapters (in-memory, Postgres) translate their own
constraint-violation shape into this same exception type so use cases stay
adapter-agnostic.
"""


class DuplicateProductSlugError(Exception):
    """Raised when registering a product whose `slug` is already taken.

    `slug` is the only DB-unique business identifier for a product (see
    `product-persistence` spec) — this mirrors the `products_slug_key`
    unique constraint.
    """

    def __init__(self, slug: str) -> None:
        super().__init__(f"Product with slug '{slug}' is already registered")
        self.slug = slug
