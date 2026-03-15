"""Tests for LangChain-agent orchestration normalization and fallbacks."""

from __future__ import annotations

from typing import Any

from app.schemas.orchestrator import (
    OrchestratorPolicyConfig,
    RecommendationToolRuntimePayload,
)
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import RecommendationQuery, RecommendationResult
from app.services.orchestrator.service import (
    OrchestratorService,
    build_runtime_state_message,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


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


def test_orchestrator_uses_agent_transcript_for_grounded_results() -> None:
    service = OrchestratorService()

    def agent_executor(_messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "messages": [
                HumanMessage(content="recommend me a summer trip"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "recommendation_query",
                            "args": {"session_id": "sess-123", "query": "summer trip"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content="Found 1 grounded option.",
                    name="recommendation_query",
                    tool_call_id="call-1",
                    artifact=_success_tool_artifact(),
                ),
                AIMessage(
                    content="Lisbon is the strongest grounded match for this trip."
                ),
            ]
        }

    response = service.handle_message(
        user_message="recommend me a summer trip",
        session_state=_base_state(),
        agent_executor=agent_executor,
    )

    assert (
        response.assistant_message
        == "Lisbon is the strongest grounded match for this trip."
    )
    assert len(response.recommendations) == 1
    assert response.recommendations[0].item_id == "dest-lisbon"
    assert response.state["status"] == "refine"
    assert response.state["last_recommendation_version"] == "heuristic-v1"


def test_orchestrator_builds_fallback_query_from_extracted_state_when_agent_fails() -> (
    None
):
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def recommendation_executor(query: RecommendationQuery):
        captured_query["value"] = query
        return {
            "ranking_version": "heuristic-v1",
            "results": [],
        }

    response = service.handle_message(
        user_message=(
            "Recommend hotels from NYC to Lisbon from 2026-06-10 to 2026-06-17 "
            "with budget between 1200 and 2400 USD."
        ),
        session_state=SessionState(session_id="sess-new"),
        agent_executor=lambda _messages: (_ for _ in ()).throw(RuntimeError("boom")),
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.constraints.origin == "NYC"
    assert query.constraints.destination == "Lisbon"
    assert query.filters["item_type"] == "hotel"
    assert response.recommendations == []
    assert "not seeing strong matches" in response.assistant_message


def test_orchestrator_returns_clarification_when_agent_skips_tool() -> None:
    service = OrchestratorService()

    def agent_executor(_messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "messages": [
                HumanMessage(content="hello"),
                AIMessage(content="Could you share your destination and dates first?"),
            ]
        }

    response = service.handle_message(
        user_message="hello",
        session_state=SessionState(session_id="sess-clarify"),
        agent_executor=agent_executor,
    )

    assert (
        response.assistant_message
        == "Could you share your destination and dates first?"
    )
    assert response.recommendations == []
    assert response.state["status"] == "explore"


def test_orchestrator_runs_fallback_recommendation_when_agent_skips_tool() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def agent_executor(_messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "messages": [
                HumanMessage(
                    content=(
                        "Recommend hotels in Lisbon from 2026-06-10 to 2026-06-17 "
                        "with budget between 1200 and 2400 USD."
                    )
                ),
                AIMessage(content="Can you share your destination and dates first?"),
            ]
        }

    def recommendation_executor(query: RecommendationQuery):
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
        user_message=(
            "Recommend hotels in Lisbon from 2026-06-10 to 2026-06-17 "
            "with budget between 1200 and 2400 USD."
        ),
        session_state=SessionState(session_id="sess-skip-tool"),
        agent_executor=agent_executor,
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.constraints.destination == "Lisbon"
    assert query.constraints.dates is not None
    assert query.constraints.dates.start.isoformat() == "2026-06-10"
    assert query.constraints.budget is not None
    assert query.constraints.budget.max == 2400.0
    assert query.filters["item_type"] == "hotel"
    assert len(response.recommendations) == 1
    assert response.recommendations[0].item_id == "hotel-lisbon-1"
    assert response.state["status"] == "refine"
    assert response.state["constraints"]["destination"] == "Lisbon"


def test_orchestrator_handles_tool_validation_error_transcript() -> None:
    service = OrchestratorService()

    def agent_executor(_messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "messages": [
                HumanMessage(content="find me something"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "recommendation_query",
                            "args": {},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content="validation error",
                    name="recommendation_query",
                    tool_call_id="call-1",
                    status="error",
                ),
                AIMessage(content="Ignore this model message."),
            ]
        }

    response = service.handle_message(
        user_message="find me something",
        session_state=SessionState(session_id="sess-invalid"),
        agent_executor=agent_executor,
    )

    assert "I am not ready to run the search yet" in response.assistant_message
    assert response.recommendations == []


def test_orchestrator_handles_tool_timeout_artifact() -> None:
    service = OrchestratorService()

    def agent_executor(_messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "messages": [
                HumanMessage(content="find me something"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "recommendation_query",
                            "args": {"session_id": "sess-timeout", "query": "x"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content="timeout",
                    name="recommendation_query",
                    tool_call_id="call-1",
                    artifact=RecommendationToolRuntimePayload(
                        status="timeout",
                        error_code="recommendation_timeout",
                        error_message="timed out",
                    ).model_dump(mode="json"),
                ),
            ]
        }

    response = service.handle_message(
        user_message="find me something",
        session_state=SessionState(session_id="sess-timeout"),
        agent_executor=agent_executor,
    )

    assert "search in time" in response.assistant_message
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
