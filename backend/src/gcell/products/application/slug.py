"""Server-derived product slugs.

Pure `slugify` plus a repository-probing dedupe loop -- see design.md
"slug generated in application/, validated only by the domain". The
domain's `Product._SLUG_PATTERN` stays the only validator: `Product.
__post_init__` re-checks whatever this module produces, so a generator bug
fails loudly at construction instead of reaching Postgres.
"""

import re
import unicodedata

from gcell.products.application.exceptions import UnslugifiableProductNameError
from gcell.products.application.repository import ProductRepository

_MAX_BASE_LENGTH = 76  # leaves room for a numeric suffix like "-999"
_MAX_SLUG_LENGTH = 80  # mirrors Product._MAX_SLUG_LENGTH / the DB check
_MAX_ATTEMPTS = 100

_NON_ALPHANUMERIC_RUN = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Derive a kebab-case slug from a product name.

    NFKD-normalizes then strips combining marks (the standard,
    lossless-for-ASCII path for a Spanish catalog -- no transliteration
    table needed), lowercases, collapses every non-alphanumeric run to a
    single hyphen, and strips leading/trailing hyphens. Truncates to
    `_MAX_BASE_LENGTH` characters, re-stripping any trailing hyphen the cut
    itself introduces.

    Raises `UnslugifiableProductNameError` if nothing alphanumeric survives
    -- never fabricates a placeholder slug.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = ascii_only.lower()
    hyphenated = _NON_ALPHANUMERIC_RUN.sub("-", lowered).strip("-")
    if not hyphenated:
        raise UnslugifiableProductNameError(name)
    return hyphenated[:_MAX_BASE_LENGTH].rstrip("-")


class SlugGenerationExhaustedError(Exception):
    """Raised when `generate_unique_slug` exhausts its bounded attempt
    budget (`_MAX_ATTEMPTS`) without finding a free candidate.

    Kept local to this module (not `exceptions.py`) -- this is a slug-
    generation-specific concern, not a repository-port-contract error.
    """

    def __init__(self, name: str, attempts: int) -> None:
        super().__init__(
            f"Could not generate a unique slug for '{name}' after {attempts} attempts"
        )
        self.name = name
        self.attempts = attempts


def _suffixed_candidate(base: str, suffix: int) -> str:
    candidate = f"{base}-{suffix}"
    overflow = len(candidate) - _MAX_SLUG_LENGTH
    if overflow > 0:
        shortened_base = base[: len(base) - overflow].rstrip("-")
        candidate = f"{shortened_base}-{suffix}"
    return candidate


async def generate_unique_slug(repository: ProductRepository, name: str) -> str:
    """Probe `base`, then `base-2`, `base-3`, ... via `slug_exists`.

    `slug_exists` deliberately ignores `deleted_at` (see design.md "retired
    slugs stay reserved"), so a retired product's slug is never handed to a
    different product. Bounded at `_MAX_ATTEMPTS` probes total.

    This probe is advisory only: `repository.add` remains the single source
    of truth for the actual uniqueness guarantee (a lost race surfaces as
    `DuplicateProductSlugError`).
    """
    base = slugify(name)
    for attempt in range(_MAX_ATTEMPTS):
        candidate = base if attempt == 0 else _suffixed_candidate(base, attempt + 1)
        if not await repository.slug_exists(candidate):
            return candidate
    raise SlugGenerationExhaustedError(name, _MAX_ATTEMPTS)
