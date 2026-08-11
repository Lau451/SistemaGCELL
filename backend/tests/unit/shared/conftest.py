"""Shared fixtures for `shared.infrastructure` unit tests.

`_stub_jwks_lookup` monkeypatches `PyJWKClient.get_signing_key_from_jwt` to
return `admin_jwt_test_support`'s throwaway TEST ES256 keypair's public key,
so `verify_admin_jwt` tests exercise the REAL decode/verify code path with
zero network calls and zero live Supabase Auth dependency — see design.md's
corrected "Testing Strategy" (ES256/JWKS, not HS256/shared-secret). It also
seeds the three `SUPABASE_JWT*`/`SUPABASE_JWKS_URL` env vars so
`verify_admin_jwt` never hits its own "not configured" fail-closed branch
during these tests.
"""

import pytest
from admin_jwt_test_support import AUDIENCE, ISSUER, JWKS_URL, TEST_PRIVATE_KEY, FakeSigningKey
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
