"""Tests for the API health endpoint."""

from app.main import app
from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_preserves_request_trace_id() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health", headers={"X-Trace-ID": "trace-health-test"})

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == "trace-health-test"
