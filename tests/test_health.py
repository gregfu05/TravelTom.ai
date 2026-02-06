"""Tests for the API health endpoint."""

from app.main import app
from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
