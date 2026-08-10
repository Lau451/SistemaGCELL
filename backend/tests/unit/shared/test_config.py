"""Unit tests for `shared.infrastructure.config.db_url`.

Pure `os.environ` read — no DB connection attempted here.
"""

from gcell.shared.infrastructure.config import db_url


def test_db_url_returns_value_when_env_var_is_set(monkeypatch) -> None:
    monkeypatch.setenv("DB_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")

    assert db_url() == "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def test_db_url_returns_none_when_env_var_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("DB_URL", raising=False)

    assert db_url() is None
