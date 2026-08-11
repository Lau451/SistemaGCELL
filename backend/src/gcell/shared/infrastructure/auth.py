"""FastAPI-facing JWT verification for the `/admin` trust boundary.

FastAPI is the ONLY trust boundary in this change (see design.md's Data
Flow) -- a forged/expired/mis-issued/mis-audienced/wrong-algorithm token
MUST be rejected here, on every request, with a single generic body so a
caller can never learn which of the four checks failed.

Local Supabase Auth signs tokens with ES256 (asymmetric, per-project key
pair), confirmed by decoding a real token before this change was
implemented -- see design.md's corrected "Decision: PyJWT, not
python-jose". Verification therefore resolves the PUBLIC signing key from
the JWKS endpoint via `PyJWKClient`, never a shared secret.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError

from gcell.shared.infrastructure.config import jwks_url, jwt_audience, jwt_issuer

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AdminIdentity:
    """The verified identity of an authenticated admin caller."""

    subject: str
    email: str | None


def _unauthorized() -> HTTPException:
    # One generic body across every failure mode -- never leak which of the
    # four checks (signature/exp/iss/aud) failed.
    return HTTPException(
        status_code=401,
        detail="invalid_token",
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache(maxsize=1)
def _get_jwks_client() -> PyJWKClient:
    """Lazily build the module-wide `PyJWKClient` on first real use.

    Caches keys across requests, same as design.md's module-level
    instance -- built lazily (not at import time) so importing this module
    never crashes when `SUPABASE_JWKS_URL` happens to be unset (e.g.
    unrelated tests importing `gcell.main`); the misconfiguration is still
    caught explicitly below and fails closed with `500`.
    """
    return PyJWKClient(jwks_url())


def verify_admin_jwt(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AdminIdentity:
    issuer, audience = jwt_issuer(), jwt_audience()
    if not issuer or not jwks_url():
        # Fail closed, never 200 -- an unconfigured deployment must not
        # silently accept every token.
        raise HTTPException(status_code=500, detail="auth_misconfigured")

    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(creds.credentials)
        claims = jwt.decode(
            creds.credentials,
            key=signing_key.key,
            algorithms=["ES256"],  # blocks alg=none / HS256-confusion
            issuer=issuer,
            audience=audience,
            options={
                "require": ["exp", "iss", "aud", "sub"],
                "verify_signature": True,
                "verify_exp": True,
            },
            leeway=0,
        )
    except (jwt.InvalidTokenError, PyJWKClientError):
        raise _unauthorized() from None

    return AdminIdentity(subject=claims["sub"], email=claims.get("email"))
