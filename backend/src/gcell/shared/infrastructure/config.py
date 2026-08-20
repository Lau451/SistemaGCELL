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


def supabase_url() -> str | None:
    """Return the Supabase project URL, or `None` if unset.

    BACKEND-ONLY (see design.md "Config") — this MUST NEVER acquire a
    `NEXT_PUBLIC_` twin; the `SUPABASE_SERVICE_ROLE_KEY` it is paired
    with bypasses RLS and must never reach the frontend bundle.
    """
    return os.environ.get("SUPABASE_URL")


def supabase_service_role_key() -> str | None:
    """Return the Supabase service_role key, or `None` if unset.

    BACKEND-ONLY — see `supabase_url()`. This is the credential the
    `shared/infrastructure/supabase_storage.py` adapter uses to write
    product image objects (design.md "Backend Service Role Upload And
    Delete Contract").
    """
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


# Never a floating alias (e.g. a `*-latest` tag): a silent model swap
# changes output shape and cost without a deploy (design.md DD4). The
# `GEMINI_MODEL` env override below turns a future deprecation into a
# config change instead.
_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def gemini_api_key() -> str | None:
    """Return the configured Gemini API key, or `None` if unset.

    BACKEND-ONLY — same rule as `supabase_service_role_key()`: this MUST
    NEVER acquire a `NEXT_PUBLIC_` twin (`test_frontend_service_role_boundary.py`
    is parametrized over `GEMINI` for exactly this reason). Never logged,
    never placed in a response body or error detail (design.md DD4:
    `502 generation_failed`/`generation_refused` are opaque).
    """
    return os.environ.get("GEMINI_API_KEY")


def gemini_model() -> str:
    """Return the configured Gemini model id.

    Defaults to `_DEFAULT_GEMINI_MODEL`, overridable by an optional
    `GEMINI_MODEL` env var (design.md DD4's model-pinning policy). The
    Gemini REST API version itself is pinned separately, in the adapter's
    base URL (`/v1beta`), not here.
    """
    return os.environ.get("GEMINI_MODEL", _DEFAULT_GEMINI_MODEL)
