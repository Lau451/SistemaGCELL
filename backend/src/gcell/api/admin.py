"""`/admin` router: JWT-gated, exposes read and write product endpoints.

Router-level `Depends(verify_admin_jwt)` runs BEFORE any path-operation
dependency (design.md's "Router wiring") -- an unauthenticated caller
always gets `401` and can never probe DB availability via `503`. Every
write route reuses this SAME router-level dependency, never a separate or
weaker check (admin-api-access spec, "Product Read And Write Endpoints").
Pydantic response models live here, in `api/`, never in
`products/domain/` -- the domain boundary test bans `pydantic` there.

Every write route calls a PR2 use case (`CreateProductUseCase`,
`UpdateProductUseCase`, `RetireProductUseCase`, `RetireVariantUseCase`),
never `PostgresProductRepository` methods directly -- `UpdateProductUseCase`
is the ONLY place that guards a variant id against belonging to a
different product before `repository.update` is called (see PR2's
apply-progress.md "Issues Found": the adapter's `ON CONFLICT` has no
`product_id` in its conflict target).

`422` for every rejected body (Pydantic `extra="forbid"` failures AND a
domain `ValueError`/`TypeError` escaping a use case); `404` for
`ProductNotFoundError`/`VariantNotFoundError`; `409` for
`DuplicateProductSlugError` -- design.md's exact table, "Decision: `422`
for every rejected body; no `400`".
"""

from collections.abc import Awaitable
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from gcell.products.application.create_product import CreateProductUseCase
from gcell.products.application.exceptions import (
    DuplicateProductSlugError,
    ProductNotFoundError,
    UnslugifiableProductNameError,
    VariantNotFoundError,
)
from gcell.products.application.retire_product import (
    RetireProductUseCase,
    RetireVariantUseCase,
)
from gcell.products.application.slug import SlugGenerationExhaustedError
from gcell.products.application.update_product import UpdateProductUseCase
from gcell.products.domain.product import Product, ProductVariant
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

async def _execute_or_raise[T](operation: Awaitable[T]) -> T:
    """Run a use case coroutine, translating application-layer exceptions
    into the exact HTTP status codes from design.md's mapping table.
    """
    try:
        return await operation
    except (
        ValueError,
        TypeError,
        UnslugifiableProductNameError,
        SlugGenerationExhaustedError,
    ) as exc:
        # A name with no alphanumeric content, or one that collides on
        # every generated slug candidate, is a rejected-body case just
        # like a domain ValueError -- design.md's table didn't enumerate
        # these two (both plain `Exception` subclasses, not ValueError),
        # which would otherwise escape as an unhandled 500.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ProductNotFoundError, VariantNotFoundError):
        # Same generic body for both -- a variant belonging to a different
        # product must never be distinguishable from an unknown id (IDOR).
        raise HTTPException(status_code=404, detail="not_found") from None
    except DuplicateProductSlugError:
        raise HTTPException(status_code=409, detail="slug_conflict") from None


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


class AdminVariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a client sending `slug` gets 422, not silence

    id: UUID | None = None  # None = new variant
    color: str
    price: Decimal
    cost: Decimal


class AdminProductWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str
    variants: list[AdminVariantInput] = []  # empty allowed -- proposal Q4


def _to_domain_variants(items: list[AdminVariantInput]) -> list[ProductVariant]:
    return [
        ProductVariant(
            id=item.id if item.id is not None else uuid4(),
            color=item.color,
            price=item.price,
            cost=item.cost,
        )
        for item in items
    ]


@router.post("/products", status_code=201)
async def create_admin_product(
    body: AdminProductWriteRequest,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> AdminProductResponse:
    async def _create() -> Product:
        async with pool.acquire() as conn:
            repository = PostgresProductRepository(conn)
            use_case = CreateProductUseCase(repository=repository)
            return await use_case.execute(
                name=body.name,
                model=body.model,
                variants=_to_domain_variants(body.variants),
            )

    product = await _execute_or_raise(_create())
    return AdminProductResponse.from_domain(product)


@router.patch("/products/{product_id}")
async def update_admin_product(
    product_id: UUID,
    body: AdminProductWriteRequest,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> AdminProductResponse:
    async def _update() -> Product:
        async with pool.acquire() as conn:
            repository = PostgresProductRepository(conn)
            use_case = UpdateProductUseCase(repository=repository)
            return await use_case.execute(
                product_id=product_id,
                name=body.name,
                model=body.model,
                variants=_to_domain_variants(body.variants),
            )

    product = await _execute_or_raise(_update())
    return AdminProductResponse.from_domain(product)


@router.delete("/products/{product_id}", status_code=204)
async def retire_admin_product(
    product_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> None:
    async def _retire() -> None:
        async with pool.acquire() as conn:
            repository = PostgresProductRepository(conn)
            use_case = RetireProductUseCase(repository=repository)
            await use_case.execute(product_id)

    await _execute_or_raise(_retire())


@router.delete("/products/{product_id}/variants/{variant_id}", status_code=204)
async def retire_admin_variant(
    product_id: UUID,
    variant_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> None:
    async def _retire() -> None:
        async with pool.acquire() as conn:
            repository = PostgresProductRepository(conn)
            use_case = RetireVariantUseCase(repository=repository)
            await use_case.execute(product_id, variant_id)

    await _execute_or_raise(_retire())
