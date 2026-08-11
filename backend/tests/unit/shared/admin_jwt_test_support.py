"""Pure JWT-forging helpers for `shared.infrastructure.auth` unit tests.

Deliberately named uniquely (NOT `conftest.py` or a name shared with any
other test directory's helper module) -- this repo's test tree has no
`__init__.py` chain, so pytest's default "prepend" import mode inserts
each test file's own directory onto `sys.path` and imports plain
top-level module names. Two different directories both exporting a module
literally named `conftest` (or any other identical name) collide in the
process-wide `sys.modules` cache the moment both are imported in the same
`pytest` invocation -- exactly what `tasks.md`'s own multi-file focused
test command does. See `conftest.py` in this directory for the fixture
that consumes these helpers.
"""

import base64
import hashlib
import hmac
import json
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ISSUER = "http://127.0.0.1:54321/auth/v1"
AUDIENCE = "authenticated"
JWKS_URL = "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json"

# Throwaway keypairs, generated once per test process — never touch any real
# Supabase signing key. `OTHER_PRIVATE_KEY` signs the "tampered signature"
# case: a token signed with a key that does NOT match the JWKS `kid`.
TEST_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


class FakeSigningKey:
    """Mimics the subset of `jwt.PyJWK` that `verify_admin_jwt` reads."""

    def __init__(self, key) -> None:
        self.key = key


def _public_key_pem_bytes(private_key) -> bytes:
    """Serialize a public key the way it would appear if copied from a
    real JWKS/PEM export — used as the HMAC secret in the algorithm-
    confusion attack case (asymmetric public key bytes reused as a
    symmetric secret).
    """
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _forge_hs256_confusion_token(payload: dict, secret_bytes: bytes) -> str:
    """Hand-craft an `alg: HS256` JWT signed with `secret_bytes`.

    PyJWT's own `encode()` deliberately REFUSES to sign with a PEM-looking
    key under HS256 (it detects the asymmetric-key-as-HMAC-secret misuse
    and raises `InvalidKeyError`) — which is exactly the real-world
    algorithm-confusion attack this test simulates from the ATTACKER's
    side, so the attacker cannot be assumed to use PyJWT's guarded API.
    Built by hand with stdlib `hmac`/`base64`/`json` instead.
    """
    header_b64 = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = header_b64 + b"." + payload_b64
    signature = hmac.new(secret_bytes, signing_input, hashlib.sha256).digest()
    return (signing_input + b"." + _b64url(signature)).decode()


def make_admin_token(
    *,
    private_key=None,
    alg: str = "ES256",
    iss: str | None = ISSUER,
    aud: str | None = AUDIENCE,
    sub: str = "11111111-1111-1111-1111-111111111111",
    exp_delta: int | None = 3600,
    include_exp: bool = True,
    extra_claims: dict | None = None,
) -> str:
    """Build a JWT for a single test case.

    `alg="HS256"` signs with `_public_key_pem_bytes(private_key)` as the
    HMAC secret — the classic asymmetric-to-symmetric algorithm-confusion
    attack `algorithms=["ES256"]` must reject.
    """
    key = private_key if private_key is not None else TEST_PRIVATE_KEY
    now = int(time.time())
    payload: dict = {"sub": sub, "iat": now}
    if iss is not None:
        payload["iss"] = iss
    if aud is not None:
        payload["aud"] = aud
    if include_exp:
        payload["exp"] = now + (exp_delta if exp_delta is not None else 0)
    if extra_claims:
        payload.update(extra_claims)

    if alg == "HS256":
        return _forge_hs256_confusion_token(payload, _public_key_pem_bytes(key))
    return jwt.encode(payload, key, algorithm=alg)
