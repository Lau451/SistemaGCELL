"""Unit tests for `shared.infrastructure.auth.verify_admin_jwt`.

Exercises `verify_admin_jwt`'s REAL decode/verify code path with zero
network calls — `conftest.py`'s `_stub_jwks_lookup` monkeypatches
`PyJWKClient.get_signing_key_from_jwt` to return the throwaway TEST ES256
keypair's public key instead of fetching JWKS over HTTP. Every negative
case MUST raise `401` with an IDENTICAL generic body — the caller must
never be able to tell which of the four checks failed.
"""

import pytest
from admin_jwt_test_support import (
    AUDIENCE,
    ISSUER,
    OTHER_PRIVATE_KEY,
    make_admin_token,
)
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from gcell.shared.infrastructure.auth import AdminIdentity, verify_admin_jwt


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_missing_token_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(None)

    assert exc_info.value.status_code == 401


def test_non_bearer_scheme_is_rejected() -> None:
    creds = HTTPAuthorizationCredentials(scheme="Basic", credentials=make_admin_token())

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(creds)

    assert exc_info.value.status_code == 401


def test_expired_token_is_rejected() -> None:
    token = make_admin_token(exp_delta=-3600)

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_wrong_issuer_is_rejected() -> None:
    token = make_admin_token(iss="https://attacker.example/auth/v1")

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_wrong_audience_is_rejected() -> None:
    token = make_admin_token(aud="not-authenticated")

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_tampered_signature_is_rejected() -> None:
    # Signed with a DIFFERENT EC keypair than the one the JWKS `kid` names
    # (the fake JWKS lookup always returns `TEST_PRIVATE_KEY`'s public key).
    token = make_admin_token(private_key=OTHER_PRIVATE_KEY)

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_missing_exp_claim_is_rejected() -> None:
    token = make_admin_token(include_exp=False)

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_algorithm_confusion_hs256_is_rejected() -> None:
    # Signed with alg=HS256 using the TEST public key's PEM bytes as the
    # HMAC secret — the classic asymmetric-to-symmetric algorithm-confusion
    # attack. `algorithms=["ES256"]` must reject it via the allowlist alone.
    token = make_admin_token(alg="HS256")

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_valid_token_on_all_four_checks_is_accepted() -> None:
    token = make_admin_token(
        sub="22222222-2222-2222-2222-222222222222",
        extra_claims={"email": "admin@gcell.local"},
    )

    identity = verify_admin_jwt(_bearer(token))

    assert identity == AdminIdentity(
        subject="22222222-2222-2222-2222-222222222222",
        email="admin@gcell.local",
    )


def test_all_rejection_reasons_share_an_identical_response_body() -> None:
    """No oracle: an attacker probing missing-token vs. expired vs. wrong-iss
    must not be able to distinguish which check failed from the body.
    """
    missing_token_exc = None
    try:
        verify_admin_jwt(None)
    except HTTPException as exc:
        missing_token_exc = exc

    expired_token_exc = None
    try:
        verify_admin_jwt(_bearer(make_admin_token(exp_delta=-3600)))
    except HTTPException as exc:
        expired_token_exc = exc

    wrong_iss_exc = None
    try:
        verify_admin_jwt(_bearer(make_admin_token(iss="https://attacker.example")))
    except HTTPException as exc:
        wrong_iss_exc = exc

    assert missing_token_exc is not None
    assert expired_token_exc is not None
    assert wrong_iss_exc is not None
    assert missing_token_exc.status_code == expired_token_exc.status_code == 401
    assert missing_token_exc.detail == expired_token_exc.detail == wrong_iss_exc.detail


def test_missing_issuer_config_fails_closed_with_500(monkeypatch) -> None:
    # Fail-closed guard: an unconfigured deployment must never silently
    # accept a token because the expected `iss` was never set.
    monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
    token = make_admin_token()

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(_bearer(token))

    assert exc_info.value.status_code == 500


def test_missing_jwks_url_config_fails_closed_with_500(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
    token = make_admin_token()

    with pytest.raises(HTTPException) as exc_info:
        verify_admin_jwt(_bearer(token))

    assert exc_info.value.status_code == 500


def test_verify_admin_jwt_uses_configured_issuer_and_audience(monkeypatch) -> None:
    # Triangulation: prove `iss`/`aud` are read from config, not hardcoded —
    # a token matching a DIFFERENT (still internally-consistent) issuer/
    # audience pair is accepted once config is repointed to match it.
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", "http://other-project/auth/v1")
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "other-audience")
    token = make_admin_token(iss="http://other-project/auth/v1", aud="other-audience")

    identity = verify_admin_jwt(_bearer(token))

    assert identity.subject == "11111111-1111-1111-1111-111111111111"
    # Sanity: the original ISSUER/AUDIENCE constants no longer match config.
    assert ISSUER != "http://other-project/auth/v1"
    assert AUDIENCE != "other-audience"
