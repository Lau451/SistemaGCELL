"""Products domain model.

Pure Python only — zero framework imports (no FastAPI, no Pydantic, no
DB/Supabase client, no SQLAlchemy, no httpx). This module IS the hexagonal
boundary that the rest of the products domain must not cross.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_MAX_SLUG_LENGTH = 80


def _validate_money(field_name: str, value: object) -> None:
    """Shared money invariant for `price`/`cost`.

    - Must be a `Decimal` (never `float` — silent precision loss).
    - Must be finite (`Decimal` accepts `NaN`/`Infinity`, money does not).
    - Must be non-negative.
    - Must not have more than 2 decimal places — `numeric(10,2)` would round
      silently and break round-trip equality with the database.
    """
    if not isinstance(value, Decimal):
        raise TypeError(
            f"ProductVariant.{field_name} must be a Decimal, not {type(value).__name__}"
        )
    if not value.is_finite():
        raise ValueError(f"ProductVariant.{field_name} must be finite")
    if value < 0:
        raise ValueError(f"ProductVariant.{field_name} cannot be negative")
    if value.as_tuple().exponent < -2:
        raise ValueError(
            f"ProductVariant.{field_name} cannot have more than 2 decimal places"
        )


@dataclass(eq=False)
class ProductVariant:
    """A sellable variant of a product (e.g. a specific color).

    Invariants:
    - `color` cannot be blank — a variant with no distinguishing color is meaningless.
    - `price`/`cost` must be non-negative, finite `Decimal` values with at most
      2 decimal places.

    Equality and hashing are based on `id` alone (not field values) — see
    `design.md` "identity, equality, and money invariants" for the rationale.
    """

    id: UUID
    color: str
    price: Decimal
    cost: Decimal

    def __post_init__(self) -> None:
        if not self.color or not self.color.strip():
            raise ValueError("ProductVariant.color cannot be blank")
        _validate_money("price", self.price)
        _validate_money("cost", self.cost)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProductVariant):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(eq=False)
class Product:
    """A catalog product composed of one or more variants.

    Invariants:
    - `name` and `model` cannot be blank.
    - `slug` must be lowercase kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`) and
      1-80 characters — mirrors `products_slug_format_check` / `_length_check`.
    - Each variant is validated independently by `ProductVariant`.

    Equality and hashing are based on `id` alone (not field values) — see
    `design.md` "identity, equality, and money invariants" for the rationale.
    """

    id: UUID
    slug: str
    name: str
    model: str
    variants: list[ProductVariant] = field(default_factory=list)
    description: str | None = None
    short_description: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Product.name cannot be blank")
        if not self.model or not self.model.strip():
            raise ValueError("Product.model cannot be blank")
        if not (1 <= len(self.slug) <= _MAX_SLUG_LENGTH) or not _SLUG_PATTERN.match(
            self.slug
        ):
            raise ValueError(
                "Product.slug must match ^[a-z0-9]+(-[a-z0-9]+)*$ and be 1-80 characters"
            )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Product):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
