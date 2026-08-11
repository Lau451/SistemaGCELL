"""Unit tests for `products/application/slug.py`.

Framework-free (no DB, no repository fakes beyond `InMemoryProductRepository`
for the collision-scheme tests) -- see design.md "slug generated in
application/, validated only by the domain".
"""

from uuid import uuid4

import pytest

from gcell.products.application.exceptions import UnslugifiableProductNameError


class TestSlugify:
    """Table-driven per design.md's exact cases."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Funda iPhone 15 Pro Máx", "funda-iphone-15-pro-max"),
            ("Niño", "nino"),
            ("Fundas & Cases!!", "fundas-cases"),
            (" --x-- ", "x"),
        ],
    )
    def test_slugify_produces_expected_kebab_case(
        self, name: str, expected: str
    ) -> None:
        from gcell.products.application.slug import slugify

        assert slugify(name) == expected

    def test_slugify_truncates_long_names_without_trailing_hyphen(self) -> None:
        from gcell.products.application.slug import slugify

        # 200 chars, with word-boundary spaces so the 76-char cut is likely
        # to land mid-hyphen-run without the rstrip("-") safety net.
        long_name = "word " * 40  # 200 chars

        result = slugify(long_name)

        assert len(result) <= 76
        assert not result.endswith("-")
        assert not result.startswith("-")

    def test_slugify_raises_when_name_has_no_alphanumeric_content(self) -> None:
        from gcell.products.application.slug import slugify

        with pytest.raises(UnslugifiableProductNameError) as exc_info:
            slugify("🎁🎁")

        assert exc_info.value.name == "🎁🎁"


class TestGenerateUniqueSlug:
    """Collision scheme via `InMemoryProductRepository` (design.md
    "Collision resolution": base, base-2, base-3, ... and retired products
    keep reserving their slug).
    """

    async def test_first_registration_keeps_the_bare_slug(self) -> None:
        from gcell.products.application.slug import generate_unique_slug
        from gcell.products.infrastructure.in_memory_product_repository import (
            InMemoryProductRepository,
        )

        repository = InMemoryProductRepository()

        slug = await generate_unique_slug(repository, "iPhone 15")

        assert slug == "iphone-15"

    async def test_same_name_three_times_yields_base_then_numeric_suffixes(
        self,
    ) -> None:
        from gcell.products.application.slug import generate_unique_slug
        from gcell.products.domain.product import Product
        from gcell.products.infrastructure.in_memory_product_repository import (
            InMemoryProductRepository,
        )

        repository = InMemoryProductRepository()

        first = await generate_unique_slug(repository, "iPhone 15")
        await repository.add(
            Product(id=uuid4(), slug=first, name="iPhone 15", model="iPhone 15")
        )
        second = await generate_unique_slug(repository, "iPhone 15")
        await repository.add(
            Product(id=uuid4(), slug=second, name="iPhone 15", model="iPhone 15")
        )
        third = await generate_unique_slug(repository, "iPhone 15")

        assert (first, second, third) == ("iphone-15", "iphone-15-2", "iphone-15-3")

    async def test_a_retired_products_slug_stays_reserved(self) -> None:
        """design.md "retired slugs stay reserved": `slug_exists` deliberately
        ignores `deleted_at`, so the next candidate after a retirement is
        still `base-2`, never the freed bare `base`.
        """
        from gcell.products.application.slug import generate_unique_slug
        from gcell.products.domain.product import Product
        from gcell.products.infrastructure.in_memory_product_repository import (
            InMemoryProductRepository,
        )

        repository = InMemoryProductRepository()
        first_slug = await generate_unique_slug(repository, "iPhone 15")
        first_product = Product(
            id=uuid4(), slug=first_slug, name="iPhone 15", model="iPhone 15"
        )
        await repository.add(first_product)

        await repository.soft_delete(first_product.id)
        next_slug = await generate_unique_slug(repository, "iPhone 15")

        assert next_slug == "iphone-15-2"

    async def test_generation_raises_after_the_bounded_attempt_budget(self) -> None:
        from gcell.products.application.slug import (
            SlugGenerationExhaustedError,
            generate_unique_slug,
        )

        class AlwaysTakenRepository:
            async def slug_exists(self, slug: str) -> bool:
                return True

        with pytest.raises(SlugGenerationExhaustedError):
            await generate_unique_slug(AlwaysTakenRepository(), "iPhone 15")
