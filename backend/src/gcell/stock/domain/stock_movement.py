"""Stock domain model.

Pure Python only -- zero framework imports (no FastAPI, no Pydantic, no
DB/Supabase client, no SQLAlchemy, no httpx, no asyncpg). This module IS the
hexagonal boundary that the rest of the stock domain must not cross.

`StockMovement` is a genuinely immutable value object (`frozen=True`) --
unlike `Product`/`ProductVariant`, which needed id-based `__eq__` because
`Product.variants` is mutable, a ledger row has no mutable fields and its id
is DB-assigned (`bigint generated always as identity`), so value equality is
correct here. See design.md "identity, equality, and money invariants".
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class MovementType(StrEnum):
    """Mirrors `stock_movements_movement_type_check`'s allowed values."""

    RESTOCK = "restock"
    SALE = "sale"
    RETURN = "return"
    BREAKAGE = "breakage"
    ADJUSTMENT = "adjustment"


_POSITIVE_ONLY = frozenset({MovementType.RESTOCK, MovementType.RETURN})
_NEGATIVE_ONLY = frozenset({MovementType.SALE, MovementType.BREAKAGE})


@dataclass(frozen=True)
class StockMovement:
    """A single append-only ledger entry against a product variant.

    Invariants (mirrors `stock_movements_sign_direction_check` exactly):
    - `quantity_delta` must be non-zero.
    - `restock`/`return` require a positive `quantity_delta`.
    - `sale`/`breakage` require a negative `quantity_delta`.
    - `adjustment` allows either sign.
    - `reason`, when provided, cannot be blank (domain-only rule -- the
      database column has no such check, since `NULL` already covers "no
      reason given").
    """

    variant_id: UUID
    movement_type: MovementType
    quantity_delta: int
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.quantity_delta == 0:
            raise ValueError("StockMovement.quantity_delta cannot be zero")
        if self.movement_type in _POSITIVE_ONLY and self.quantity_delta < 0:
            raise ValueError(
                f"StockMovement.quantity_delta must be positive for "
                f"movement_type={self.movement_type!r}"
            )
        if self.movement_type in _NEGATIVE_ONLY and self.quantity_delta > 0:
            raise ValueError(
                f"StockMovement.quantity_delta must be negative for "
                f"movement_type={self.movement_type!r}"
            )
        if self.reason is not None and not self.reason.strip():
            raise ValueError("StockMovement.reason cannot be blank when provided")
