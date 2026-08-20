"""Unit tests for `shared.infrastructure.dependencies.require_db_pool` and
`require_gemini`.

Scoped to `/admin` routes only (design.md's "per-request 503 dependency
guard, not startup abort") -- a `None` pool/unset key must reject with
`503`, never raise/crash, so `lifespan`'s existing `DB_URL`-unset tolerance
stays intact. `require_gemini` mirrors `require_storage`'s exact shape
(design.md DD4: byte-for-byte `require_storage` precedent, D7).
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from gcell.shared.infrastructure.dependencies import require_db_pool, require_gemini


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


def test_require_gemini_raises_503_when_api_key_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        require_gemini()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "gemini_unavailable"


def test_require_gemini_returns_credentials_when_api_key_is_set(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    credentials = require_gemini()

    assert credentials.api_key == "gemini-key"
    assert credentials.model == "gemini-2.5-flash"


def test_require_gemini_uses_gemini_model_env_override(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")

    credentials = require_gemini()

    assert credentials.model == "gemini-2.5-pro"
