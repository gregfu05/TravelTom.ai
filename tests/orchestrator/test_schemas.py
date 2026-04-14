"""Schema validation tests for orchestrator session and tool payloads."""

from __future__ import annotations

import pytest
from app.schemas.state import SessionState
from app.schemas.tools.catalog import CatalogSearchQuery
from app.schemas.tools.events import EventPayload
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationToolResponse,
)
from pydantic import ValidationError


def test_session_state_validates_canonical_payload() -> None:
    payload = {
        "state_version": "v1",
        "session_id": "sess-123",
        "user_id": "user-456",
        "constraints": {
            "destination": "LIS",
            "dates": {"start": "2026-06-10", "end": "2026-06-17"},
            "trip_length_days": 7,
            "budget": {"min": 1000, "max": 2500, "currency": "USD"},
            "party_size": {"adults": 2, "children": 0},
        },
        "preferences": {
            "weighted_interests": {"museums": 0.8, "food": 0.6},
            "dislikes": ["red_eye_flights"],
        },
        "entities": {"destinations": ["Lisbon"]},
        "shortlist": ["item-1"],
        "itinerary": {"days": [{"day": 1, "title": "Arrival"}]},
        "status": "explore",
        "last_recommendation_version": "heuristic-v1",
        "last_message_at": "2026-02-04T12:00:00Z",
    }

    state = SessionState.model_validate(payload)
    assert state.session_id == "sess-123"
    assert state.constraints.destination == "LIS"
    assert state.preferences.weighted_interests["museums"] == 0.8
    assert state.itinerary.days[0]["day"] == 1


def test_session_state_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        SessionState.model_validate({"session_id": "sess-1", "status": "unknown"})


def test_session_state_rejects_invalid_interest_weight() -> None:
    with pytest.raises(ValidationError):
        SessionState.model_validate(
            {
                "session_id": "sess-1",
                "preferences": {"weighted_interests": {"food": 1.4}},
            }
        )


def test_session_state_rejects_invalid_date_range() -> None:
    with pytest.raises(ValidationError):
        SessionState.model_validate(
            {
                "session_id": "sess-1",
                "constraints": {"dates": {"start": "2026-06-17", "end": "2026-06-10"}},
            }
        )


def test_recommendation_query_defaults_and_validation() -> None:
    payload = {
        "session_id": "sess-123",
        "query": "week in portugal",
        "constraints": {
            "destination": "LIS",
            "dates": {"start": "2026-06-10", "end": "2026-06-17"},
            "budget": {"min": 1000, "max": 2500, "currency": "USD"},
            "party_size": {"adults": 2, "children": 0},
        },
    }
    query = RecommendationQuery.model_validate(payload)
    assert query.max_results == 20
    assert query.ranking_version == "heuristic-v1"


def test_recommendation_query_rejects_invalid_max_results() -> None:
    with pytest.raises(ValidationError):
        RecommendationQuery.model_validate(
            {"session_id": "sess-1", "query": "trip", "max_results": 1000}
        )


def test_recommendation_tool_response_allows_empty_results() -> None:
    response = RecommendationToolResponse.model_validate(
        {"results": [], "ranking_version": "heuristic-v1"}
    )
    assert response.results == []


def test_catalog_search_query_supports_type_alias() -> None:
    query = CatalogSearchQuery.model_validate(
        {"q": "lisbon dinner", "type": "restaurant", "limit": 10, "offset": 0}
    )
    assert query.item_type == "restaurant"


def test_event_payload_requires_idempotency_key() -> None:
    with pytest.raises(ValidationError):
        EventPayload.model_validate(
            {
                "event_id": "evt-1",
                "event_type": "ui.click",
                "event_version": 1,
                "occurred_at": "2026-02-04T12:00:00Z",
                "session_id": "sess-1",
                "payload": {},
            }
        )
