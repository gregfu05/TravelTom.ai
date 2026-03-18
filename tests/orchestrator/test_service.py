"""Tests for chat-agent orchestration and deterministic follow-up shaping."""

from __future__ import annotations

from typing import Any

from app.schemas.orchestrator import (
    OrchestratorPolicyConfig,
    RecommendationToolRuntimePayload,
    TranscriptMessage,
)
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)
from app.services.orchestrator.service import (
    OrchestratorService,
    build_runtime_state_message,
)
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage


def _base_state() -> SessionState:
    return SessionState.model_validate(
        {
            "session_id": "sess-123",
            "constraints": {
                "destination": "Lisbon",
                "dates": {"start": "2026-06-10", "end": "2026-06-17"},
                "budget": {"min": 1000, "max": 2500, "currency": "USD"},
            },
            "preferences": {"weighted_interests": {"nightlife": 0.8}},
            "conversation": {
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "hotel Lisbon nightlife",
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
                    "item_id": "hotel-lisbon-1",
                    "item_type": "hotel",
                    "score": 0.92,
                    "rank": 1,
                    "features": {"name": "Lisbon Stay"},
                    "explanation": "Strong nightlife fit.",
                }
            ],
        },
    ).model_dump(mode="json")


def test_build_chat_messages_includes_hidden_context_and_recent_transcript() -> None:
    service = OrchestratorService()

    messages = service.build_chat_messages(
        user_message="show me more",
        session_state=_base_state(),
        recent_messages=[
            TranscriptMessage(role="user", content="Find me a hotel in Lisbon"),
            TranscriptMessage(role="assistant", content="Here are grounded options."),
        ],
    )

    assert messages[0]["role"] == "system"
    assert messages[0]["content"].startswith("TRAVELTOM_SESSION_STATE_JSON:")
    assert messages[1]["role"] == "system"
    assert "TRAVELTOM_RECOMMENDATION_CONTEXT_JSON:" in messages[1]["content"]
    assert '"effective_item_type": "hotel"' in messages[1]["content"]
    assert (
        '"effective_query": "show me more hotel Lisbon nightlife"'
        in messages[1]["content"]
    )
    assert messages[2] == {"role": "user", "content": "Find me a hotel in Lisbon"}
    assert messages[3] == {"role": "assistant", "content": "Here are grounded options."}
    assert messages[4] == {"role": "user", "content": "show me more"}


def test_orchestrator_follow_up_uses_carried_item_type_and_query() -> None:
    service = OrchestratorService()
    captured: dict[str, Any] = {}

    def agent_executor(messages: list[dict[str, str]]) -> dict[str, Any]:
        captured["messages"] = messages
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "recommendation_query",
                            "args": {
                                "session_id": "sess-123",
                                "query": "show me more hotel Lisbon nightlife",
                                "constraints": {
                                    "destination": "Lisbon",
                                    "dates": {
                                        "start": "2026-06-10",
                                        "end": "2026-06-17",
                                    },
                                    "budget": {
                                        "min": 1000,
                                        "max": 2500,
                                        "currency": "USD",
                                    },
                                },
                                "filters": {"item_type": "hotel"},
                                "max_results": 5,
                                "ranking_version": "heuristic-v1",
                            },
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
                AIMessage(content="Here is another grounded hotel option in Lisbon."),
            ]
        }

    response = service.handle_message(
        user_message="show me more",
        session_state=_base_state(),
        recent_messages=[
            TranscriptMessage(role="user", content="Find me a hotel in Lisbon"),
            TranscriptMessage(role="assistant", content="Here are grounded options."),
        ],
        agent_executor=agent_executor,
    )

    assert captured["messages"][-1]["content"] == "show me more"
    assert (
        response.assistant_message == "Here is another grounded hotel option in Lisbon."
    )
    assert response.recommendations[0].item_id == "hotel-lisbon-1"
    assert response.state["conversation"]["last_recommendation_item_type"] == "hotel"
    assert (
        response.state["conversation"]["last_recommendation_query"]
        == "show me more hotel Lisbon nightlife"
    )
    assert response.state["status"] == "refine"


def test_orchestrator_fallback_preserves_prior_topic_terms_for_follow_up() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "hotel-lisbon-2",
                        "item_type": "hotel",
                        "score": 0.9,
                        "rank": 1,
                        "features": {"name": "Late Night Stay"},
                        "explanation": "Better nightlife fit.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="another option",
        session_state=_base_state(),
        agent_executor=lambda _messages: (_ for _ in ()).throw(RuntimeError("boom")),
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.filters["item_type"] == "hotel"
    assert query.query == "another option hotel Lisbon nightlife"
    assert response.state["conversation"]["last_recommendation_query"] == query.query
    assert response.recommendations[0].item_id == "hotel-lisbon-2"


def test_orchestrator_explicit_override_replaces_carried_item_type() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "flight-lisbon-1",
                        "item_type": "flight",
                        "score": 0.88,
                        "rank": 1,
                        "features": {"name": "LIS Flight"},
                        "explanation": "Switches to flights explicitly.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="actually flights",
        session_state=_base_state(),
        agent_executor=lambda _messages: (_ for _ in ()).throw(RuntimeError("boom")),
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.filters["item_type"] == "flight"
    assert query.query == "actually flights"
    assert response.state["conversation"]["last_recommendation_item_type"] == "flight"
    assert response.recommendations[0].item_type == "flight"


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
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="What travel dates should I plan around?")]
        },
    )

    assert response.state["constraints"]["destination"] == "Lisbon"
    assert "travel dates" in response.assistant_message
    assert response.state["conversation"]["last_requested_slots"] == ["dates"]
    assert response.state["conversation"]["last_user_intent"] == "recommend"


def test_orchestrator_handles_invalid_tool_payload_with_safe_copy() -> None:
    service = OrchestratorService()

    response = service.handle_message(
        user_message=(
            "recommend a trip to Lisbon from 2026-06-10 to 2026-06-17 " "under 2400 USD"
        ),
        session_state=SessionState(session_id="sess-invalid-tool"),
        agent_executor=lambda _messages: {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "recommendation_query",
                            "args": {"query": "bad"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content="invalid",
                    name="recommendation_query",
                    tool_call_id="call-1",
                    artifact={"status": "invalid_payload"},
                ),
            ]
        },
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
    assert payload.response.results[0].item_id == "hotel-lisbon-1"
