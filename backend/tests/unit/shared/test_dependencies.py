"""Unit tests for `shared.infrastructure.dependencies.require_db_pool`.

Scoped to `/admin` routes only (design.md's "per-request 503 dependency
guard, not startup abort") -- a `None` pool must reject with `503`, never
raise/crash, so `lifespan`'s existing `DB_URL`-unset tolerance stays intact.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from gcell.shared.infrastructure.dependencies import require_db_pool


def _request_with_pool(pool):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=pool)))


def test_require_db_pool_raises_503_when_pool_is_none() -> None:
    request = _request_with_pool(None)

    with pytest.raises(HTTPException) as exc_info:
        require_db_pool(request)

    assert exc_info.value.status_code == 503


def test_require_db_pool_returns_pool_when_configured() -> None:
    sentinel_pool = object()
    request = _request_with_pool(sentinel_pool)

    assert require_db_pool(request) is sentinel_pool
