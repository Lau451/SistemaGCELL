"""Integration test for the `/health` endpoint via FastAPI's TestClient."""

from fastapi.testclient import TestClient

from gcell.main import app


def test_health_returns_ok() -> None:
    # Context-managed so the lifespan actually runs -- constructing
    # `TestClient` without `with` silently skips lifespan entirely, which
    # would let a broken lifespan ship green.
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
