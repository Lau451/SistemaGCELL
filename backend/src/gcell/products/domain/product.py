"""Products domain model.

Pure Python only — zero framework imports (no FastAPI, no Pydantic, no
DB/Supabase client, no SQLAlchemy, no httpx). This module IS the hexagonal
boundary that the rest of the products domain must not cross.
"""

from dataclasses import dataclass, field


@dataclass
class ProductVariant:
    """A sellable variant of a product (e.g. a phone case for one model).

    Invariants:
    - `phone_model` cannot be blank — a variant that fits no phone is meaningless.
    - `price` and `cost` cannot be negative — money cannot go below zero here.
    """

    phone_model: str
    price: float
    cost: float

    def __post_init__(self) -> None:
        if not self.phone_model or not self.phone_model.strip():
            raise ValueError("ProductVariant.phone_model cannot be blank")
        if self.price < 0:
            raise ValueError("ProductVariant.price cannot be negative")
        if self.cost < 0:
            raise ValueError("ProductVariant.cost cannot be negative")


@dataclass
class Product:
    """A catalog product composed of one or more variants.

    Invariants:
    - `name` cannot be blank.
    - Each variant is validated independently by `ProductVariant`.
    """

    name: str
    variants: list[ProductVariant] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Product.name cannot be blank")
