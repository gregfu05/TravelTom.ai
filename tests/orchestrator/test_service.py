"""Tests for planner/composer orchestration and deterministic fallbacks."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage, ToolMessage

from app.schemas.orchestrator import (
    LLMComposedResponse,
    LLMOrchestrationPlan,
    OrchestratorPolicyConfig,
    RecommendationToolRuntimePayload,
    TranscriptMessage,
)
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import RecommendationQuery, RecommendationResult
from app.services.orchestrator.service import (
    OrchestratorService,
    build_runtime_state_message,
)


def _base_state() -> SessionState:
    return SessionState.model_validate(
        {
            "session_id": "sess-123",
            "constraints": {
                "destination": "Lisbon",
                "dates": {"start": "2026-06-10", "end": "2026-06-17"},
                "budget": {"min": 1000, "max": 2500, "currency": "USD"},
            },
            "conversation": {"last_user_intent": "recommend"},
        }
    )


def _success_tool_artifact() -> dict[str, Any]:
    return RecommendationToolRuntimePayload(
        status="success",
        response={
            "ranking_version": "heuristic-v1",
            "results": [
                {
                    "item_id": "dest-lisbon",
                    "item_type": "destination",
                    "score": 0.92,
                    "rank": 1,
                    "features": {"name": "Lisbon"},
                    "explanation": "Strong culture and food fit.",
                }
            ],
        },
    ).model_dump(mode="json")


def test_orchestrator_uses_planner_and_composer_with_recent_transcript() -> None:
    service = OrchestratorService()
    captured: dict[str, str] = {}

    def planner_executor(prompt_context: str) -> LLMOrchestrationPlan:
        captured["planner"] = prompt_context
        return LLMOrchestrationPlan.model_validate(
            {
                "intent": "refine",
                "should_call_recommendation_tool": True,
                "state_patch": {
                    "preferences": {"weighted_interests": {"nightlife": 0.9}},
                    "status": "refine",
                },
                "query_controls": {"query": "another option with more nightlife"},
            }
        )

    def recommendation_executor(_query: RecommendationQuery) -> dict[str, Any]:
        return {
            "ranking_version": "heuristic-v1",
            "results": [
                {
                    "item_id": "dest-lisbon",
                    "item_type": "destination",
                    "score": 0.92,
                    "rank": 1,
                    "features": {"name": "Lisbon"},
                    "explanation": "Strong culture and nightlife fit.",
                }
            ],
        }

    def composer_executor(prompt_context: str) -> LLMComposedResponse:
        captured["composer"] = prompt_context
        return LLMComposedResponse(
            assistant_message="Lisbon is still the best grounded fit, with a stronger nightlife angle."
        )

    response = service.handle_message(
        user_message="another option with more nightlife",
        session_state=_base_state(),
        recent_messages=[
            TranscriptMessage(role="user", content="Recommend me a summer city trip."),
            TranscriptMessage(
                role="assistant",
                content="Lisbon is the strongest grounded match so far.",
            ),
        ],
        planner_executor=planner_executor,
        composer_executor=composer_executor,
        recommendation_executor=recommendation_executor,
    )

    assert "Recent transcript" in captured["planner"]
    assert "Recommend me a summer city trip." in captured["planner"]
    assert "Recommendation records" in captured["composer"]
    assert "name=Lisbon" in captured["composer"]
    assert (
        response.assistant_message
        == "Lisbon is still the best grounded fit, with a stronger nightlife angle."
    )
    assert len(response.recommendations) == 1
    assert response.state["status"] == "refine"
    assert response.state["preferences"]["weighted_interests"]["nightlife"] == 0.9
    assert response.state["conversation"]["last_user_intent"] == "refine"
    assert response.state["conversation"]["last_requested_slots"] == []


def test_orchestrator_progressive_clarification_acknowledges_new_detail() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-clarify",
            "conversation": {
                "last_requested_slots": ["destination"],
                "last_user_intent": "recommend",
            },
        }
    )

    response = service.handle_message(
        user_message="Lisbon",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant", content="Which destination should I focus on?"
            )
        ],
    )

    assert response.state["constraints"]["destination"] == "Lisbon"
    assert "I have your destination" in response.assistant_message
    assert "travel dates" in response.assistant_message
    assert "budget range" not in response.assistant_message
    assert response.state["conversation"]["last_requested_slots"] == ["dates"]
    assert response.state["conversation"]["last_user_intent"] == "recommend"


def test_orchestrator_continues_recommendation_flow_when_final_slot_arrives() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}
    state = SessionState.model_validate(
        {
            "session_id": "sess-complete",
            "constraints": {
                "destination": "Lisbon",
                "dates": {"start": "2026-06-10", "end": "2026-06-17"},
            },
            "conversation": {
                "last_requested_slots": ["budget"],
                "last_user_intent": "recommend",
            },
        }
    )

    def recommendation_executor(query: RecommendationQuery) -> dict[str, Any]:
        captured_query["value"] = query
        return {
            "ranking_version": "heuristic-v1",
            "results": [
                {
                    "item_id": "hotel-lisbon-1",
                    "item_type": "hotel",
                    "score": 0.94,
                    "rank": 1,
                    "features": {"name": "Lisbon Stay"},
                    "explanation": "Strong hotel match in Lisbon.",
                }
            ],
        }

    response = service.handle_message(
        user_message="Budget between 1200 and 2400 USD.",
        session_state=state,
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.constraints.destination == "Lisbon"
    assert query.constraints.budget is not None
    assert query.constraints.budget.max == 2400.0
    assert response.state["status"] == "refine"
    assert response.state["conversation"]["last_user_intent"] == "recommend"
    assert response.state["conversation"]["last_requested_slots"] == []
    assert response.recommendations[0].item_id == "hotel-lisbon-1"


def test_orchestrator_refine_turn_preserves_prior_context() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}
    state = _base_state()
    state.status = "refine"
    state.conversation.last_user_intent = "refine"

    def recommendation_executor(query: RecommendationQuery) -> dict[str, Any]:
        captured_query["value"] = query
        return {
            "ranking_version": "heuristic-v1",
            "results": [
                {
                    "item_id": "dest-porto",
                    "item_type": "destination",
                    "score": 0.9,
                    "rank": 1,
                    "features": {"name": "Porto"},
                    "explanation": "A slightly cheaper nightlife-focused alternative.",
                }
            ],
        }

    response = service.handle_message(
        user_message="cheaper with more nightlife",
        session_state=state,
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.constraints.destination == "Lisbon"
    assert query.constraints.dates is not None
    assert response.state["preferences"]["weighted_interests"]["nightlife"] == 0.8
    assert response.state["status"] == "refine"
    assert response.recommendations[0].item_id == "dest-porto"


def test_orchestrator_handles_invalid_tool_payload_with_safe_copy() -> None:
    service = OrchestratorService()

    response = service.handle_message(
        user_message="recommend a trip to Lisbon from 2026-06-10 to 2026-06-17 under 2400 USD",
        session_state=SessionState(session_id="sess-invalid-tool"),
        recommendation_executor=lambda _query: {"results": []},
    )

    assert "invalid recommendation payload" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_build_results_message_falls_back_to_item_id_without_name() -> (
    None
):
    service = OrchestratorService()
    message = service.build_results_message(
        [
            RecommendationResult.model_validate(
                {
                    "item_id": "dest-lisbon",
                    "item_type": "destination",
                    "score": 0.93,
                    "rank": 1,
                    "features": {},
                    "explanation": "Strong match for culture and food.",
                }
            )
        ]
    )

    assert "My top picks are:\n1. dest-lisbon" in message


def test_orchestrator_extracts_direct_recommendation_payload_from_tool_message() -> (
    None
):
    service = OrchestratorService(
        policy_config=OrchestratorPolicyConfig(max_recommendation_results=3)
    )
    agent_result = {
        "messages": [
            SystemMessage(
                content=build_runtime_state_message(SessionState(session_id="sess-1"))
            ),
            ToolMessage(
                content="Found 1 grounded option.",
                name="recommendation_query",
                tool_call_id="call-1",
                artifact=_success_tool_artifact(),
            ),
        ]
    }

    payload = service.response_from_direct_agent_result(agent_result=agent_result)

    assert payload.status == "success"
    assert payload.response is not None
    assert payload.response.results[0].item_id == "dest-lisbon"
