"""Integration test for the `/health` endpoint via FastAPI's TestClient."""

from fastapi.testclient import TestClient

from gcell.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
