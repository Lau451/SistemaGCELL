"""Errors raised by the stock application layer.

Kept here (not in `domain/`) -- same rationale as
`products/application/exceptions.py`: these describe how the repository
port reacts to a persistence-time conflict, not a domain invariant.
"""

from datetime import datetime
from uuid import UUID


class UnknownVariantError(Exception):
    """Raised when recording a movement against a `variant_id` that does not
    exist, mirroring `stock_movements_variant_id_fkey`.
    """

    def __init__(self, variant_id: UUID) -> None:
        super().__init__(f"No product variant exists with id '{variant_id}'")
        self.variant_id = variant_id


class InvertedDateRangeError(ValueError):
    """Raised by `ListVariantStockMovementsUseCase` when a normalized
    `since` is later than a normalized `until` (design.md D10). A
    `ValueError` subclass so the existing `_execute_or_raise` helper in
    `api/admin.py` maps it to `422` with no new `except` arm -- mirrors
    how every other application-layer validation failure already becomes
    a rejected-body response.
    """

    def __init__(self, since: datetime, until: datetime) -> None:
        super().__init__(
            f"since ({since.isoformat()}) is after until ({until.isoformat()})"
        )
        self.since = since
        self.until = until
