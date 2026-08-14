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
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from gcell.products.application.create_product import CreateProductUseCase
from gcell.products.application.delete_product_image import DeleteProductImageUseCase
from gcell.products.application.exceptions import (
    DuplicateProductSlugError,
    ImageNotFoundError,
    ImageTooLargeError,
    ProductNotFoundError,
    UnslugifiableProductNameError,
    UnsupportedImageError,
    VariantNotFoundError,
)
from gcell.products.application.reorder_product_image import ReorderProductImageUseCase
from gcell.products.application.retire_product import (
    RetireProductUseCase,
    RetireVariantUseCase,
)
from gcell.products.application.slug import SlugGenerationExhaustedError
from gcell.products.application.update_product import UpdateProductUseCase
from gcell.products.application.upload_product_image import UploadProductImageUseCase
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.domain.product_image import ProductImage
from gcell.products.infrastructure.postgres_product_image_repository import (
    PostgresProductImageRepository,
)
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.shared.application.object_storage import ObjectStorageError
from gcell.shared.infrastructure.auth import verify_admin_jwt
from gcell.shared.infrastructure.dependencies import (
    StorageCredentials,
    require_db_pool,
    require_storage,
)
from gcell.shared.infrastructure.pillow_image_normalizer import PillowImageNormalizer
from gcell.shared.infrastructure.supabase_storage import SupabaseStorage

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
        UnsupportedImageError,
        ImageTooLargeError,
    ) as exc:
        # A name with no alphanumeric content, or one that collides on
        # every generated slug candidate, is a rejected-body case just
        # like a domain ValueError -- design.md's table didn't enumerate
        # these two (both plain `Exception` subclasses, not ValueError),
        # which would otherwise escape as an unhandled 500. An unsupported
        # or oversized image upload is the same class of rejected-body
        # case (admin-product-images spec "Upload Validation Runs Before
        # Any Storage Write").
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ProductNotFoundError, VariantNotFoundError, ImageNotFoundError):
        # Same generic body for all three -- a variant/image belonging to
        # a different product must never be distinguishable from an
        # unknown id (IDOR). `ImageNotFoundError` also covers a foreign id
        # inside a reorder request's ordered list.
        raise HTTPException(status_code=404, detail="not_found") from None
    except DuplicateProductSlugError:
        raise HTTPException(status_code=409, detail="slug_conflict") from None
    except ObjectStorageError as exc:
        # A genuine (non-404) Storage failure that escapes the use case --
        # design.md's status-mapping table, "NEW 502 ObjectStorageError".
        raise HTTPException(status_code=502, detail="storage_error") from exc


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


@router.get("/products/{product_id}")
async def get_admin_product(
    product_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> AdminProductResponse:
    # Added post-PR3: design.md's File Changes table always specified this
    # route, but it was missed from tasks.md's Phase 3 breakdown -- PR4's
    # edit page needs it directly rather than list-and-filter. Reuses
    # `get_by_id` (unchanged since PR1, already excludes soft-deleted rows).
    async with pool.acquire() as conn:
        product = await PostgresProductRepository(conn).get_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="not_found")
    return AdminProductResponse.from_domain(product)


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


# ---------------------------------------------------------------------------
# Product images (design.md "Endpoints"). `require_storage` is a dependency
# ONLY on upload and delete -- the only two use cases that construct an
# `ObjectStorage` adapter. GET and the reorder PUT never touch Storage
# (admin-product-images spec "Reorder Replaces The Product's Whole Image
# Order In One Call" -- "no Storage object MUST be modified"), so a
# missing Supabase Storage config must never block listing or reordering.
# Where both apply, dependency order
# stays 401 (router-level) -> `require_db_pool` 503 -> `require_storage`
# 503, matching design.md's status-mapping section exactly.
# ---------------------------------------------------------------------------


class AdminProductImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: UUID | None
    storage_path: str
    alt_text: str | None
    sort_order: int

    @classmethod
    def from_domain(cls, image: ProductImage) -> "AdminProductImageResponse":
        return cls(
            id=image.id,
            product_id=image.product_id,
            variant_id=image.variant_id,
            storage_path=image.storage_path,
            alt_text=image.alt_text,
            sort_order=image.sort_order,
        )


def _build_storage(credentials: StorageCredentials) -> SupabaseStorage:
    return SupabaseStorage(
        url=credentials.url,
        service_role_key=credentials.service_role_key,
    )


@router.get("/products/{product_id}/images")
async def list_admin_product_images(
    product_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> list[AdminProductImageResponse]:
    async with pool.acquire() as conn:
        images = await PostgresProductImageRepository(conn).list_for_product(product_id)
    return [AdminProductImageResponse.from_domain(image) for image in images]


@router.post("/products/{product_id}/images", status_code=201)
async def upload_admin_product_image(
    product_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
    storage_credentials: Annotated[StorageCredentials, Depends(require_storage)],
    file: UploadFile,
    variant_id: Annotated[UUID | None, Form()] = None,
    alt_text: Annotated[str | None, Form()] = None,
) -> AdminProductImageResponse:
    data = await file.read()

    async def _upload() -> ProductImage:
        async with pool.acquire() as conn:
            use_case = UploadProductImageUseCase(
                image_repository=PostgresProductImageRepository(conn),
                product_repository=PostgresProductRepository(conn),
                object_storage=_build_storage(storage_credentials),
                normalizer=PillowImageNormalizer(),
            )
            return await use_case.execute(
                product_id=product_id,
                data=data,
                variant_id=variant_id,
                alt_text=alt_text,
            )

    image = await _execute_or_raise(_upload())
    return AdminProductImageResponse.from_domain(image)


@router.delete("/products/{product_id}/images/{image_id}", status_code=204)
async def delete_admin_product_image(
    product_id: UUID,
    image_id: UUID,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
    storage_credentials: Annotated[StorageCredentials, Depends(require_storage)],
) -> None:
    async def _delete() -> None:
        async with pool.acquire() as conn:
            use_case = DeleteProductImageUseCase(
                image_repository=PostgresProductImageRepository(conn),
                object_storage=_build_storage(storage_credentials),
            )
            await use_case.execute(product_id, image_id)

    await _execute_or_raise(_delete())


class AdminReorderImagesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_ids: list[UUID]


@router.put("/products/{product_id}/images/order")
async def reorder_admin_product_images(
    product_id: UUID,
    body: AdminReorderImagesRequest,
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> list[AdminProductImageResponse]:
    async def _reorder() -> list[ProductImage]:
        async with pool.acquire() as conn:
            use_case = ReorderProductImageUseCase(
                image_repository=PostgresProductImageRepository(conn)
            )
            return await use_case.execute(product_id, body.image_ids)

    images = await _execute_or_raise(_reorder())
    return [AdminProductImageResponse.from_domain(image) for image in images]
