"""Tests for orchestrator routing and tool fallback behavior."""

from __future__ import annotations

import time

from app.schemas.state import SessionState
from app.schemas.tools.recommendations import RecommendationToolResponse
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


def test_orchestrator_calls_recommendation_tool_for_recommend_intent() -> None:
    tool_calls: dict[str, object] = {"count": 0, "query": None}

    def tool(query):
        tool_calls["count"] = int(tool_calls["count"]) + 1
        tool_calls["query"] = query
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

    service = OrchestratorService(recommendation_tool=tool)
    response = service.handle_message(
        user_message="recommend me a summer trip",
        session_state=_base_state(),
    )

    assert tool_calls["count"] == 1
    assert response.recommendations[0].item_id == "dest-lisbon"
    assert "Top picks" in response.assistant_message
    assert response.state["status"] == "refine"


def test_orchestrator_returns_clarification_when_intent_is_unclear() -> None:
    tool_calls = {"count": 0}

    def tool(query):
        tool_calls["count"] += 1
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(recommendation_tool=tool)
    response = service.handle_message(
        user_message="hello",
        session_state=_base_state().model_copy(update={"status": "explore"}),
    )

    assert tool_calls["count"] == 0
    assert "optimize for" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_handles_tool_timeout_with_retry_prompt() -> None:
    def slow_tool(query):
        time.sleep(0.05)
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(
        recommendation_tool=slow_tool,
        policy_config=OrchestratorPolicyConfig(recommendation_timeout_seconds=0.01),
    )
    response = service.handle_message(
        user_message="suggest hotels",
        session_state=_base_state(),
    )

    assert "in time" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_handles_invalid_tool_payload() -> None:
    def invalid_payload_tool(query):
        return {"results": [{"item_id": "x"}]}

    service = OrchestratorService(recommendation_tool=invalid_payload_tool)
    response = service.handle_message(
        user_message="recommend beaches",
        session_state=_base_state(),
    )

    assert "invalid recommendation payload" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_requests_more_constraints_on_empty_results() -> None:
    def empty_results_tool(query):
        return {"ranking_version": "heuristic-v1", "results": []}

    service = OrchestratorService(recommendation_tool=empty_results_tool)
    response = service.handle_message(
        user_message="recommend a trip",
        session_state=_base_state().model_copy(
            update={
                "constraints": _base_state().constraints.model_copy(
                    update={"budget": None}
                )
            }
        ),
    )

    assert "do not have strong matches yet" in response.assistant_message
    assert "budget range" in response.assistant_message
    assert response.state["status"] == "explore"


def test_orchestrator_exposes_langchain_runtime_flag() -> None:
    service = OrchestratorService()
    assert isinstance(service.uses_langchain, bool)
