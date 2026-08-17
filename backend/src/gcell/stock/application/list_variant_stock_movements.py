"""Use case: list a variant's stock movement history, scoped to a
`product_id`, with the same ownership (IDOR) guard as
`RecordVariantStockMovementUseCase` -- a `variant_id` that does not exist,
or that belongs to a different product, raises `VariantNotFoundError`
BEFORE any `history_reader` call, never a distinguishable outcome (spec:
admin-stock-management "Movement History Ownership Is Checked Before Any
Read"). The ownership guard also runs BEFORE the `since`/`until`
normalization and the inverted-range check below (design.md, D10) -- a
foreign `variant_id` combined with an inverted range must still raise
`VariantNotFoundError`, never leak that the range was rejected first.

`limit` is clamped here (`max(1, min(limit, 100))`, default 20), not via
FastAPI `Query(le=100)` validation -- design.md Decision 3 says clamp, not
reject. The reader is asked for `limit + 1` rows and the result trimmed to
`limit`, so `next_before_id` is `None` exactly when the true end of the
ledger was reached, rather than after a wasted extra round-trip on the next
click.

`since`/`until` (design.md DD1, D10, D11) are optional `datetime`s,
validated/clamped here -- the same idiom as `limit` -- never via FastAPI's
declarative `Query()` mechanism. A naive value (no `tzinfo`) is normalized
to UTC. A naive `until` landing at exactly midnight is further expanded to
`+1 day - 1 microsecond`, so a date-only `until` means "through the end of
that day" (D11) even for a hand-written API call, not only through the
UI's already-offset-aware instant. `since` later than `until` (after
normalization) raises `InvertedDateRangeError` -- a `ValueError` subclass
mapped to `422` by the existing `_execute_or_raise` helper in
`api/admin.py`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from gcell.products.application.exceptions import ProductNotFoundError, VariantNotFoundError
from gcell.products.application.repository import ProductRepository
from gcell.stock.application.exceptions import InvertedDateRangeError
from gcell.stock.application.stock_movement_history_reader import (
    RecordedStockMovement,
    StockMovementHistoryReader,
)

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100
_MIDNIGHT = time(0, 0, 0, 0)


def _normalize_since(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _normalize_until(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    was_naive_at_midnight = value.tzinfo is None and value.time() == _MIDNIGHT
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if was_naive_at_midnight:
        value = value + timedelta(days=1) - timedelta(microseconds=1)
    return value


@dataclass(frozen=True)
class StockMovementPage:
    items: list[RecordedStockMovement]
    next_before_id: int | None


@dataclass
class ListVariantStockMovementsUseCase:
    products: ProductRepository
    history_reader: StockMovementHistoryReader

    async def execute(
        self,
        product_id: UUID,
        variant_id: UUID,
        limit: int = _DEFAULT_LIMIT,
        before_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> StockMovementPage:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        if not any(variant.id == variant_id for variant in product.variants):
            raise VariantNotFoundError(variant_id, product_id)  # never 403 (IDOR)

        normalized_since = _normalize_since(since)
        normalized_until = _normalize_until(until)
        if (
            normalized_since is not None
            and normalized_until is not None
            and normalized_since > normalized_until
        ):
            raise InvertedDateRangeError(normalized_since, normalized_until)

        effective_limit = max(1, min(limit, _MAX_LIMIT))
        rows = await self.history_reader.list_for_variant(
            variant_id,
            effective_limit + 1,
            before_id,
            normalized_since,
            normalized_until,
        )

        if len(rows) > effective_limit:
            trimmed = rows[:effective_limit]
            return StockMovementPage(items=trimmed, next_before_id=trimmed[-1].id)
        return StockMovementPage(items=rows, next_before_id=None)
