"""Port-shape proof for `StockMovementRepository`.

Spec's "Repository port has no mutation path" scenario: the append-only
invariant is a TYPE-level fact, not a runtime check -- mirrors the frontend's
`CatalogRelation` allowlist pattern (see design.md "append-only is a
port-shape fact"). This test inspects the `Protocol`'s own declared members
directly (not an instance), so it fails the moment anyone adds an `update`
or `delete` method to the port, even before any adapter implements it.
"""

from gcell.stock.application.repository import StockMovementRepository


def test_repository_port_declares_exactly_one_method_record() -> None:
    public_members = {
        name for name in vars(StockMovementRepository) if not name.startswith("_")
    }

    assert public_members == {"record"}
