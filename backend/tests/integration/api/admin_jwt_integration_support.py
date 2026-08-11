"""JWT-forging helper for `/admin` router integration tests.

Deliberately named uniquely across the whole test tree (not `conftest.py`
or any name reused elsewhere) — see
`tests/unit/shared/admin_jwt_test_support.py`'s docstring for why: this
repo's test tree has no `__init__.py` chain, so identically-named modules
in different directories collide in the process-wide `sys.modules` cache
when both get imported in the same `pytest` invocation.
"""

import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

ISSUER = "http://127.0.0.1:54321/auth/v1"
AUDIENCE = "authenticated"
JWKS_URL = "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json"

TEST_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


class FakeSigningKey:
    def __init__(self, key) -> None:
        self.key = key


def make_valid_admin_token(sub: str = "11111111-1111-1111-1111-111111111111") -> str:
    now = int(time.time())
    payload = {"sub": sub, "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 3600}
    return jwt.encode(payload, TEST_PRIVATE_KEY, algorithm="ES256")
