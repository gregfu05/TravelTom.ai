"""Tests for the recommendations query endpoint."""

from __future__ import annotations

from typing import Any

from app.api.v1.recommendations import get_recommendation_tool
from app.main import app
from fastapi.testclient import TestClient


def _base_payload() -> dict[str, Any]:
    return {
        "session_id": "session-123",
        "query": "week in portugal",
        "constraints": {
            "destination": "LIS",
            "dates": {"start": "2026-06-10", "end": "2026-06-17"},
            "budget": {"min": 1000, "max": 2500, "currency": "USD"},
            "party_size": {"adults": 2, "children": 0},
        },
        "max_results": 10,
        "ranking_version": "heuristic-v1",
    }


def test_recommendations_query_returns_placeholder_response() -> None:
    def _fake_recommendation_tool(query):
        del query
        return {
            "ranking_version": "heuristic-v1",
            "results": [
                {
                    "item_id": "restaurant-1",
                    "item_type": "restaurant",
                    "score": 0.91,
                    "rank": 1,
                    "features": {"name": "Example"},
                    "explanation": "Deterministic sample result.",
                }
            ],
        }

    app.dependency_overrides[get_recommendation_tool] = (
        lambda: _fake_recommendation_tool
    )
    try:
        client = TestClient(app)
        response = client.post("/api/v1/recommendations/query", json=_base_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["results"], list)
    assert len(body["results"]) <= _base_payload()["max_results"]
    assert body["ranking_version"] == "heuristic-v1"
    assert "score" not in body["results"][0]
    assert "explanation" not in body["results"][0]


def test_recommendations_query_rejects_invalid_payload() -> None:
    payload = _base_payload()
    payload["max_results"] = 500

    client = TestClient(app)
    response = client.post("/api/v1/recommendations/query", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_recommendations_query_handles_invalid_tool_response() -> None:
    def _invalid_recommendation_tool(query):
        del query
        return {"ranking_version": "heuristic-v1", "results": [{"item_id": 123}]}

    app.dependency_overrides[get_recommendation_tool] = (
        lambda: _invalid_recommendation_tool
    )
    try:
        client = TestClient(app)
        response = client.post("/api/v1/recommendations/query", json=_base_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert (
        response.json()["error"]["message"] == "Invalid recommendation service response"
    )
