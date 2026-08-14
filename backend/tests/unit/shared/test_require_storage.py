"""Unit tests for `shared.infrastructure.dependencies.require_storage`.

Mirrors `require_db_pool`'s existing shape and test style exactly (see
`test_dependencies.py`) -- a `503` per-request guard, never a crash, for
`/admin` image routes that need Supabase Storage config.
"""

import pytest
from fastapi import HTTPException

from gcell.shared.infrastructure.dependencies import require_storage


def test_require_storage_raises_503_when_url_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

    with pytest.raises(HTTPException) as exc_info:
        require_storage()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "storage_unavailable"


def test_require_storage_raises_503_when_service_role_key_is_unset(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        require_storage()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "storage_unavailable"


def test_require_storage_raises_503_when_both_are_unset(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        require_storage()

    assert exc_info.value.status_code == 503


def test_require_storage_returns_credentials_when_both_are_set(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

    credentials = require_storage()

    assert credentials.url == "http://127.0.0.1:54321"
    assert credentials.service_role_key == "service-role-key"
