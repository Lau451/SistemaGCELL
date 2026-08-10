"""Errors raised by the stock application layer.

Kept here (not in `domain/`) -- same rationale as
`products/application/exceptions.py`: these describe how the repository
port reacts to a persistence-time conflict, not a domain invariant.
"""

from uuid import UUID


class UnknownVariantError(Exception):
    """Raised when recording a movement against a `variant_id` that does not
    exist, mirroring `stock_movements_variant_id_fkey`.
    """

    def __init__(self, variant_id: UUID) -> None:
        super().__init__(f"No product variant exists with id '{variant_id}'")
        self.variant_id = variant_id
