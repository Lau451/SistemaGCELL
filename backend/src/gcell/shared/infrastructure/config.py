"""Environment-backed configuration for `shared/infrastructure`.

No dotenv dependency: `os.environ` is the single source of truth. A local
`.env` (gitignored, see `.env.example`) is expected to be loaded by the
shell/tooling that starts the process, not by this module.
"""

import os


def db_url() -> str | None:
    """Return the configured Postgres DSN, or `None` if `DB_URL` is unset."""
    return os.environ.get("DB_URL")


def jwks_url() -> str | None:
    """Return the Supabase Auth JWKS endpoint URL, or `None` if unset.

    Verification uses the PUBLIC key served here (`PyJWKClient`), never a
    shared secret — the local Supabase Auth instance signs tokens with
    ES256 (asymmetric), not HS256.
    """
    return os.environ.get("SUPABASE_JWKS_URL")


def jwt_issuer() -> str | None:
    """Return the expected JWT `iss` claim, or `None` if unset."""
    return os.environ.get("SUPABASE_JWT_ISSUER")


def jwt_audience() -> str:
    """Return the expected JWT `aud` claim.

    Defaults to `"authenticated"` — Supabase Auth's standard audience for
    logged-in users, confirmed against a real local token.
    """
    return os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated")
