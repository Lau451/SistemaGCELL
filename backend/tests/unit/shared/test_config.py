"""Unit tests for `shared.infrastructure.config`.

Pure `os.environ` reads — no DB connection or HTTP call attempted here.
"""

from gcell.shared.infrastructure.config import (
    db_url,
    jwks_url,
    jwt_audience,
    jwt_issuer,
)


def test_db_url_returns_value_when_env_var_is_set(monkeypatch) -> None:
    monkeypatch.setenv("DB_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")

    assert db_url() == "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def test_db_url_returns_none_when_env_var_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("DB_URL", raising=False)

    assert db_url() is None


def test_jwks_url_returns_value_when_env_var_is_set(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_JWKS_URL", "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json")

    assert jwks_url() == "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json"


def test_jwks_url_returns_none_when_env_var_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)

    assert jwks_url() is None


def test_jwt_issuer_returns_value_when_env_var_is_set(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", "http://127.0.0.1:54321/auth/v1")

    assert jwt_issuer() == "http://127.0.0.1:54321/auth/v1"


def test_jwt_issuer_returns_none_when_env_var_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)

    assert jwt_issuer() is None


def test_jwt_audience_returns_value_when_env_var_is_set(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "custom-audience")

    assert jwt_audience() == "custom-audience"


def test_jwt_audience_defaults_to_authenticated_when_env_var_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_JWT_AUDIENCE", raising=False)

    assert jwt_audience() == "authenticated"
