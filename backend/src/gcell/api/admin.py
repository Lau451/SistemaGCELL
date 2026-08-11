"""`/admin` router: JWT-gated, exposes exactly one read-only proof endpoint.

Router-level `Depends(verify_admin_jwt)` runs BEFORE any path-operation
dependency (design.md's "Router wiring") -- an unauthenticated caller
always gets `401` and can never probe DB availability via `503`.
Pydantic response models live here, in `api/`, never in
`products/domain/` -- the domain boundary test bans `pydantic` there.
"""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from gcell.products.domain.product import Product
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.shared.infrastructure.auth import verify_admin_jwt
from gcell.shared.infrastructure.dependencies import require_db_pool

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_jwt)],
)


class AdminProductVariantResponse(BaseModel):
    id: UUID
    color: str
    price: Decimal
    cost: Decimal


class AdminProductResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    model: str
    variants: list[AdminProductVariantResponse]

    @classmethod
    def from_domain(cls, product: Product) -> "AdminProductResponse":
        return cls(
            id=product.id,
            slug=product.slug,
            name=product.name,
            model=product.model,
            variants=[
                AdminProductVariantResponse(
                    id=variant.id,
                    color=variant.color,
                    price=variant.price,
                    cost=variant.cost,
                )
                for variant in product.variants
            ],
        )


@router.get("/products")
async def list_admin_products(
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> list[AdminProductResponse]:
    async with pool.acquire() as conn:
        products = await PostgresProductRepository(conn).list_all()
    return [AdminProductResponse.from_domain(product) for product in products]
