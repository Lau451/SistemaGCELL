"""Use case: record a single stock movement through the `StockMovementRepository` port."""

from dataclasses import dataclass
from uuid import UUID

from gcell.stock.application.repository import StockMovementRepository
from gcell.stock.domain.stock_movement import MovementType, StockMovement


@dataclass
class RecordStockMovementUseCase:
    """Resolves primitives into a validated `StockMovement` before recording it.

    Takes `movement_type` as a plain `str` (never a `MovementType`) because
    callers (a future admin route, a webhook) hand over untyped input. The
    `str -> MovementType` resolution raises `ValueError` on an unknown type,
    and the resulting `StockMovement.__post_init__` enforces the sign-
    direction invariant -- both happen BEFORE `repository.record` is ever
    called, so invalid input never reaches persistence (see spec's "Movement
    Type And Sign Are Validated In The Domain" requirement).
    """

    repository: StockMovementRepository

    async def execute(
        self,
        variant_id: UUID,
        movement_type: str,
        quantity_delta: int,
        reason: str | None = None,
    ) -> StockMovement:
        try:
            resolved_type = MovementType(movement_type)
        except ValueError as exc:
            raise ValueError(f"Unknown movement_type: {movement_type!r}") from exc

        movement = StockMovement(
            variant_id=variant_id,
            movement_type=resolved_type,
            quantity_delta=quantity_delta,
            reason=reason,
        )
        await self.repository.record(movement)
        return movement
