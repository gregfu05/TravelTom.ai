"""Tests for LLM-first orchestrator behavior and deterministic guardrails."""

from __future__ import annotations

import time
from typing import Any

from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationToolResponse,
)
from app.services.orchestrator.policies import OrchestratorPolicyConfig
from app.services.orchestrator.service import OrchestratorService


def _base_state() -> SessionState:
    return SessionState.model_validate(
        {
            "session_id": "sess-123",
            "constraints": {
                "destination": "LIS",
                "dates": {"start": "2026-06-10", "end": "2026-06-17"},
                "budget": {"min": 1000, "max": 2500, "currency": "USD"},
            },
        }
    )


def test_orchestrator_uses_llm_plan_for_tool_call_and_state_updates() -> None:
    tool_count: dict[str, int] = {"value": 0}
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}
    planning_payloads: list[dict[str, Any]] = []
    response_payloads: list[dict[str, Any]] = []

    def planning_model(payload: dict[str, Any]) -> dict[str, Any]:
        planning_payloads.append(payload)
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {
                "constraints": {
                    "origin": "NYC",
                    "destination": "Lisbon",
                    "dates": {"start": "2026-06-10", "end": "2026-06-17"},
                    "budget": {"min": 1200, "max": 2400, "currency": "USD"},
                }
            },
            "query_controls": {
                "query": "summer culture trip",
                "filters": {"item_type": "destination"},
                "max_results": 4,
            },
        }

    def response_model(payload: dict[str, Any]) -> dict[str, str]:
        response_payloads.append(payload)
        return {"assistant_message": "Here are the best fits for Lisbon."}

    def tool(query: RecommendationQuery) -> RecommendationToolResponse:
        tool_count["value"] += 1
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "dest-lisbon",
                        "item_type": "destination",
                        "score": 0.92,
                        "rank": 1,
                        "features": {"interest_match": 0.8},
                        "explanation": "Strong culture and food fit.",
                    }
                ],
            }
        )

    service = OrchestratorService(
        recommendation_tool=tool,
        planning_model=planning_model,
        response_model=response_model,
    )
    response = service.handle_message(
        user_message="recommend me a summer trip",
        session_state=SessionState(session_id="sess-new"),
    )

    assert len(planning_payloads) == 1
    assert "TravelTom orchestration planner" in planning_payloads[0]["prompt"]
    assert tool_count["value"] == 1
    query = captured_query["value"]
    assert query is not None
    assert query.query == "summer culture trip"
    assert query.constraints.origin == "NYC"
    assert query.constraints.destination == "Lisbon"
    assert query.constraints.dates is not None
    assert query.constraints.budget is not None
    assert query.constraints.budget.max == 2400.0
    assert query.filters["item_type"] == "destination"
    assert query.max_results == 4
    assert response.assistant_message == "Here are the best fits for Lisbon."
    assert response.recommendations[0].item_id == "dest-lisbon"
    assert response.state["status"] == "refine"
    assert len(response_payloads) == 1
    assert "TravelTom response composer" in response_payloads[0]["prompt"]


def test_orchestrator_applies_guardrail_extraction_when_plan_is_sparse() -> None:
    captured_query: dict[str, RecommendationQuery | None] = {"query": None}

    def planning_model(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {},
        }

    def tool(query: RecommendationQuery) -> dict[str, Any]:
        captured_query["query"] = query
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(
        recommendation_tool=tool,
        planning_model=planning_model,
    )
    response = service.handle_message(
        user_message=(
            "Recommend a trip from NYC to Lisbon from 2026-06-10 to 2026-06-17 "
            "with budget between 1200 and 2400 USD."
        ),
        session_state=SessionState(session_id="sess-new"),
    )

    query = captured_query["query"]
    assert query is not None
    assert query.constraints.origin == "NYC"
    assert query.constraints.destination == "Lisbon"
    assert query.constraints.dates is not None
    assert query.constraints.dates.start.isoformat() == "2026-06-10"
    assert query.constraints.dates.end.isoformat() == "2026-06-17"
    assert query.constraints.budget is not None
    assert query.constraints.budget.min == 1200.0
    assert query.constraints.budget.max == 2400.0
    assert response.state["constraints"]["destination"] == "Lisbon"
    assert response.state["constraints"]["origin"] == "NYC"


def test_orchestrator_returns_llm_clarification_without_tool_call() -> None:
    tool_calls = {"count": 0}

    def planning_model(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": "clarify",
            "should_call_recommendation_tool": False,
            "clarification_message": "Could you share destination and dates first?",
        }

    def tool(_query: RecommendationQuery) -> dict[str, Any]:
        tool_calls["count"] += 1
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(
        recommendation_tool=tool,
        planning_model=planning_model,
    )
    response = service.handle_message(
        user_message="hello",
        session_state=SessionState(session_id="sess-clarify"),
    )

    assert tool_calls["count"] == 0
    assert response.assistant_message == "Could you share destination and dates first?"
    assert response.recommendations == []
    assert response.state["status"] == "explore"


def test_orchestrator_falls_back_when_planning_model_raises() -> None:
    tool_calls = {"count": 0}

    def failing_planner(_payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("model unavailable")

    def tool(_query: RecommendationQuery) -> dict[str, Any]:
        tool_calls["count"] += 1
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(
        recommendation_tool=tool,
        planning_model=failing_planner,
    )
    response = service.handle_message(
        user_message="recommend a trip",
        session_state=_base_state(),
    )

    assert tool_calls["count"] == 1
    assert "do not have strong matches yet" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_handles_invalid_planning_payload() -> None:
    tool_calls = {"count": 0}

    def invalid_planner(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"intent": "recommend"}

    def tool(_query: RecommendationQuery) -> dict[str, Any]:
        tool_calls["count"] += 1
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(
        recommendation_tool=tool,
        planning_model=invalid_planner,
    )
    response = service.handle_message(
        user_message="hello",
        session_state=SessionState(session_id="sess-invalid-plan"),
    )

    assert tool_calls["count"] == 0
    assert "destination" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_handles_tool_timeout_with_retry_prompt() -> None:
    def planning_model(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {},
        }

    def slow_tool(_query: RecommendationQuery) -> dict[str, Any]:
        time.sleep(0.05)
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(
        recommendation_tool=slow_tool,
        planning_model=planning_model,
        policy_config=OrchestratorPolicyConfig(recommendation_timeout_seconds=0.01),
    )
    response = service.handle_message(
        user_message="suggest hotels",
        session_state=_base_state(),
    )

    assert "in time" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_handles_invalid_tool_payload() -> None:
    def planning_model(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {},
        }

    def invalid_payload_tool(_query: RecommendationQuery) -> dict[str, Any]:
        return {"results": [{"item_id": "x"}]}

    service = OrchestratorService(
        recommendation_tool=invalid_payload_tool,
        planning_model=planning_model,
    )
    response = service.handle_message(
        user_message="recommend beaches",
        session_state=_base_state(),
    )

    assert "invalid recommendation payload" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_handles_response_model_validation_errors() -> None:
    def planning_model(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {},
        }

    def invalid_response_model(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"unexpected": "value"}

    def tool(_query: RecommendationQuery) -> dict[str, Any]:
        return {
            "ranking_version": "heuristic-v1",
            "results": [
                {
                    "item_id": "dest-lisbon",
                    "item_type": "destination",
                    "score": 0.93,
                    "rank": 1,
                    "features": {"interest_match": 0.9},
                    "explanation": "Strong match for culture and food.",
                }
            ],
        }

    service = OrchestratorService(
        recommendation_tool=tool,
        planning_model=planning_model,
        response_model=invalid_response_model,
    )
    response = service.handle_message(
        user_message="recommend me something fun",
        session_state=_base_state(),
    )

    assert "Top picks: destination:dest-lisbon." in response.assistant_message
    assert response.recommendations[0].item_id == "dest-lisbon"


def test_orchestrator_extracts_hotel_filter_from_message() -> None:
    captured_query: dict[str, RecommendationQuery | None] = {"query": None}

    def planning_model(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {},
        }

    def tool(query: RecommendationQuery) -> dict[str, Any]:
        captured_query["query"] = query
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(
        recommendation_tool=tool,
        planning_model=planning_model,
    )
    service.handle_message(
        user_message="Recommend me hotels in Santa Barbara",
        session_state=SessionState(session_id="sess-hotels"),
    )

    query = captured_query["query"]
    assert query is not None
    assert query.filters["item_type"] == "hotel"
    assert query.constraints.destination == "Santa Barbara"


def test_orchestrator_exposes_langchain_runtime_flag() -> None:
    service = OrchestratorService()
    assert isinstance(service.uses_langchain, bool)
