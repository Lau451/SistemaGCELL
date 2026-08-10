"""Environment-backed configuration for `shared/infrastructure`.

No dotenv dependency: `os.environ` is the single source of truth. A local
`.env` (gitignored, see `.env.example`) is expected to be loaded by the
shell/tooling that starts the process, not by this module.
"""

import os


def db_url() -> str | None:
    """Return the configured Postgres DSN, or `None` if `DB_URL` is unset."""
    return os.environ.get("DB_URL")
