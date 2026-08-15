"""Port-shape proof for `StockMovementHistoryReader`.

`list_for_variant` is the only member -- this is a NEW, separate read port
from `StockMovementRepository` (whose own port-shape proof in
`test_stock_movement_repository_port.py` still asserts only `record`). See
design.md Decision 2 ("Read and write adapters are already split for the
same ledger data") and spec's "StockMovementRepository gains no new
method" scenario -- this test proves the new port's shape, the sibling test
proves the old port was never touched.
"""

from gcell.stock.application.stock_movement_history_reader import StockMovementHistoryReader


def test_history_reader_port_declares_exactly_one_method_list_for_variant() -> None:
    public_members = {
        name for name in vars(StockMovementHistoryReader) if not name.startswith("_")
    }

    assert public_members == {"list_for_variant"}
