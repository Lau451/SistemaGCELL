"""Shared fixtures for `tests/integration/api`.

Mirrors `tests/unit/shared/conftest.py`'s JWKS stub so integration tests
never hit a live Supabase Auth service either.
"""

import pytest
from admin_jwt_integration_support import (
    AUDIENCE,
    ISSUER,
    JWKS_URL,
    TEST_PRIVATE_KEY,
    FakeSigningKey,
)
from jwt import PyJWKClient


@pytest.fixture(autouse=True)
def _stub_jwks_lookup(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWKS_URL", JWKS_URL)
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", ISSUER)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", AUDIENCE)
    monkeypatch.setattr(
        PyJWKClient,
        "get_signing_key_from_jwt",
        lambda self, token: FakeSigningKey(TEST_PRIVATE_KEY.public_key()),
    )
