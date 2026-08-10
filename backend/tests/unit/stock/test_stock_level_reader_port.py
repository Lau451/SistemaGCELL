"""Port-shape proof for `StockLevelReader`.

`quantity_on_hand` is the only member -- current stock is a derived read
model backed by the `variant_stock_levels` view, never a field hydrated onto
`ProductVariant` (see design.md "current stock is read via a separate
query" / spec's "ProductVariant does not carry stock" scenario).
"""

from gcell.stock.application.stock_level_reader import StockLevelReader


def test_reader_port_declares_exactly_one_method_quantity_on_hand() -> None:
    public_members = {
        name for name in vars(StockLevelReader) if not name.startswith("_")
    }

    assert public_members == {"quantity_on_hand"}
