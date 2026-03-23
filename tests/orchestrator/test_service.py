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
    PlannerExecutionError,
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


def test_orchestrator_planner_prompt_includes_transcript_and_deterministic_hints() -> (
    None
):
    service = OrchestratorService()
    captured_prompt: dict[str, str] = {}
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def planner_executor(prompt: str) -> dict[str, Any]:
        captured_prompt["value"] = prompt
        return {
            "intent": "refine",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {"filters": {"item_type": "hotel"}},
        }

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "hotel-lisbon-4",
                        "item_type": "hotel",
                        "score": 0.9,
                        "rank": 1,
                        "features": {"name": "Planner Prompt Hotel"},
                        "explanation": "Uses carried query context.",
                    }
                ],
            }
        )

    service.handle_message(
        user_message="show me more",
        session_state=_base_state(),
        recent_messages=[
            TranscriptMessage(role="user", content="Find me a hotel in Lisbon"),
            TranscriptMessage(role="assistant", content="Here are grounded options."),
        ],
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="Need more detail")]},
        recommendation_executor=recommendation_executor,
    )

    assert "Latest user message: show me more" in captured_prompt["value"]
    assert "user: Find me a hotel in Lisbon" in captured_prompt["value"]
    assert "assistant: Here are grounded options." in captured_prompt["value"]
    assert '"effective_query":"show me more hotel Lisbon nightlife"' in captured_prompt["value"]
    assert '"effective_item_type":"hotel"' in captured_prompt["value"]
    query = captured_query["value"]
    assert query is not None
    assert query.query == "show me more hotel Lisbon nightlife"


def test_orchestrator_planner_prompt_truncates_long_transcript_messages() -> None:
    service = OrchestratorService()
    captured_prompt: dict[str, str] = {}
    long_assistant_message = "Top picks: " + "very long grounded result. " * 30

    def planner_executor(prompt: str) -> dict[str, Any]:
        captured_prompt["value"] = prompt
        return {
            "intent": "clarify",
            "should_call_recommendation_tool": False,
            "clarification_message": "What should I adjust?",
        }

    response = service.handle_message(
        user_message="show me more",
        session_state=_base_state(),
        recent_messages=[
            TranscriptMessage(role="assistant", content=long_assistant_message),
        ],
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="Need more detail")]},
        recommendation_executor=None,
    )

    assert response.assistant_message
    assert response.recommendations == []
    assert long_assistant_message not in captured_prompt["value"]
    assert "assistant: Top picks:" in captured_prompt["value"]
    assert "..." in captured_prompt["value"]


def test_orchestrator_planner_state_patch_updates_state_before_agent_execution() -> (
    None
):
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-planner-slot",
            "conversation": {
                "last_requested_slots": ["destination"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "recommend hotels with food",
            },
        }
    )
    captured_messages: dict[str, list[dict[str, str]]] = {}

    def agent_executor(messages: list[dict[str, str]]) -> dict[str, Any]:
        captured_messages["value"] = messages
        return {"messages": [AIMessage(content="What travel dates should I plan around?")]}

    response = service.handle_message(
        user_message="We can base this around Kyoto",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant", content="Which destination should I focus on?"
            )
        ],
        planner_executor=lambda _prompt: {
            "intent": "recommend",
            "should_call_recommendation_tool": False,
            "clarification_message": "What travel dates should I plan around?",
            "state_patch": {"constraints": {"destination": "Kyoto"}},
            "query_controls": {"filters": {"item_type": "hotel"}},
        },
        agent_executor=agent_executor,
    )

    assert '"destination": "Kyoto"' in captured_messages["value"][0]["content"]
    assert '"effective_item_type": "hotel"' in captured_messages["value"][1]["content"]
    assert response.state["constraints"]["destination"] == "Kyoto"
    assert response.state["conversation"]["last_requested_slots"] == ["dates"]
    assert response.state["conversation"]["last_user_intent"] == "recommend"
    assert "travel dates" in response.assistant_message


def test_orchestrator_invalid_planner_patch_falls_back_to_deterministic_state() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-invalid-planner",
            "conversation": {
                "last_requested_slots": ["destination"],
                "last_user_intent": "recommend",
            },
        }
    )
    captured_messages: dict[str, list[dict[str, str]]] = {}

    def agent_executor(messages: list[dict[str, str]]) -> dict[str, Any]:
        captured_messages["value"] = messages
        return {"messages": [AIMessage(content="What travel dates should I plan around?")]}

    response = service.handle_message(
        user_message="Lisbon",
        session_state=state,
        planner_executor=lambda _prompt: {
            "intent": "recommend",
            "should_call_recommendation_tool": False,
            "state_patch": {
                "constraints": {
                    "budget": {"min": 1000, "max": 10, "currency": "USD"}
                }
            },
        },
        agent_executor=agent_executor,
    )

    assert '"destination": "Lisbon"' in captured_messages["value"][0]["content"]
    assert response.state["constraints"]["destination"] == "Lisbon"
    assert response.state["conversation"]["last_requested_slots"] == ["dates"]
    assert "travel dates" in response.assistant_message


def test_orchestrator_logs_planner_failure_and_falls_back_safely(caplog: Any) -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-planner-failure",
            "conversation": {
                "last_requested_slots": ["destination"],
                "last_user_intent": "recommend",
            },
        }
    )

    def planner_executor(_prompt: str) -> dict[str, Any]:
        raise PlannerExecutionError("planner transport failed")

    with caplog.at_level("WARNING"):
        response = service.handle_message(
            user_message="Santa Barbara",
            session_state=state,
            planner_executor=planner_executor,
            agent_executor=lambda _messages: {
                "messages": [AIMessage(content="What travel dates should I plan around?")]
            },
        )

    assert response.state["constraints"]["destination"] == "Santa Barbara"
    assert any(
        record.message == "planner_execution_failed" for record in caplog.records
    )


def test_orchestrator_planner_query_controls_drive_recommendation_fallback() -> None:
    service = OrchestratorService()
    captured_messages: dict[str, list[dict[str, str]]] = {}
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def agent_executor(messages: list[dict[str, str]]) -> dict[str, Any]:
        captured_messages["value"] = messages
        return {"messages": [AIMessage(content="Tell me more")]}

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "hotel-lisbon-5",
                        "item_type": "hotel",
                        "score": 0.91,
                        "rank": 1,
                        "features": {"name": "Planner Override Hotel"},
                        "explanation": "Planner query controls shaped the fallback.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="show me more",
        session_state=_base_state(),
        planner_executor=lambda _prompt: {
            "intent": "refine",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {
                "query": "quiet hotel Lisbon with food",
                "filters": {"item_type": "hotel"},
                "max_results": 3,
            },
        },
        agent_executor=agent_executor,
        recommendation_executor=recommendation_executor,
    )

    assert '"effective_query": "quiet hotel Lisbon with food"' in captured_messages["value"][1]["content"]
    assert '"effective_item_type": "hotel"' in captured_messages["value"][1]["content"]
    query = captured_query["value"]
    assert query is not None
    assert query.query == "quiet hotel Lisbon with food"
    assert query.filters["item_type"] == "hotel"
    assert query.max_results == 3
    assert response.state["conversation"]["last_recommendation_query"] == query.query
    assert response.state["conversation"]["last_recommendation_item_type"] == "hotel"


def test_orchestrator_meta_turn_does_not_auto_trigger_search() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-meta-search",
            "constraints": {"destination": "Santa Barbara"},
            "conversation": {
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "destination",
                "last_recommendation_query": "recommend something in santa barbara",
                "last_recommendation_result_ids": ["dest-1", "dest-2"],
            },
            "status": "refine",
        }
    )
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {"ranking_version": "heuristic-v1", "results": []}
        )

    response = service.handle_message(
        user_message="what do you mean by destination",
        session_state=state,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    assert captured_query["value"] is None
    assert response.recommendations == []
    assert "By destination" in response.assistant_message


def test_orchestrator_repair_turn_does_not_auto_trigger_search() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-repair-search",
            "constraints": {"destination": "Santa Barbara"},
            "conversation": {
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "destination",
                "last_recommendation_query": "recommend something in santa barbara",
                "last_recommendation_result_ids": ["dest-1", "dest-2"],
            },
            "status": "refine",
        }
    )
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {"ranking_version": "heuristic-v1", "results": []}
        )

    response = service.handle_message(
        user_message="not restaurants, more like sightseeing",
        session_state=state,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    assert captured_query["value"] is None
    assert response.recommendations == []
    assert "I will not assume restaurants" in response.assistant_message


def test_orchestrator_show_me_more_prefers_unseen_results() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-more-unseen",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-06-10", "end": "2026-06-17"},
                "budget": {"min": 100, "max": 900, "currency": "USD"},
            },
            "conversation": {
                "last_user_intent": "refine",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "hotel santa barbara",
                "last_recommendation_result_ids": [
                    "hotel-1",
                    "hotel-2",
                    "hotel-3",
                    "hotel-4",
                    "hotel-5",
                ],
            },
            "status": "refine",
        }
    )
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
                        "item_id": f"hotel-{index}",
                        "item_type": "hotel",
                        "score": 1.0 - (index / 100),
                        "rank": index,
                        "features": {"name": f"Hotel {index}"},
                        "explanation": f"Hotel {index}",
                    }
                    for index in range(1, 11)
                ],
            }
        )

    response = service.handle_message(
        user_message="show me more",
        session_state=state,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.max_results == 10
    assert [item.item_id for item in response.recommendations] == [
        "hotel-6",
        "hotel-7",
        "hotel-8",
        "hotel-9",
        "hotel-10",
    ]
    assert response.state["conversation"]["last_recommendation_result_ids"] == [
        "hotel-6",
        "hotel-7",
        "hotel-8",
        "hotel-9",
        "hotel-10",
    ]


def test_orchestrator_show_me_more_reports_when_only_duplicates_exist() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-more-duplicates",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-06-10", "end": "2026-06-17"},
                "budget": {"min": 100, "max": 900, "currency": "USD"},
            },
            "conversation": {
                "last_user_intent": "refine",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "hotel santa barbara",
                "last_recommendation_result_ids": [
                    "hotel-1",
                    "hotel-2",
                    "hotel-3",
                    "hotel-4",
                    "hotel-5",
                ],
            },
            "status": "refine",
        }
    )

    response = service.handle_message(
        user_message="show me more",
        session_state=state,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=lambda query: RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": f"hotel-{index}",
                        "item_type": "hotel",
                        "score": 1.0 - (index / 100),
                        "rank": index,
                        "features": {"name": f"Hotel {index}"},
                        "explanation": f"Hotel {index}",
                    }
                    for index in range(1, 6)
                ],
            }
        ),
    )

    assert response.recommendations == []
    assert "do not have new grounded options" in response.assistant_message
    assert response.state["conversation"]["last_recommendation_result_ids"] == [
        "hotel-1",
        "hotel-2",
        "hotel-3",
        "hotel-4",
        "hotel-5",
    ]


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
    assert response.assistant_message.startswith(
        "I found 1 grounded option(s) that fit what you asked for."
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


def test_orchestrator_greeting_and_meta_turns_do_not_persist_destination() -> None:
    service = OrchestratorService()
    state = SessionState(session_id="sess-meta")

    first_response = service.handle_message(
        user_message="Hello Tommy",
        session_state=state,
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="Which destination should I focus on?")]
        },
    )

    assert first_response.assistant_message == "Which destination should I focus on?"
    assert first_response.state["constraints"].get("destination") is None
    assert first_response.state["entities"]["destinations"] == []
    assert first_response.state["conversation"]["last_requested_slots"] == [
        "destination"
    ]
    assert first_response.state["conversation"]["last_user_intent"] == "clarify"
    assert (
        first_response.state["conversation"]["last_recommendation_item_type"] is None
    )
    assert first_response.state["conversation"]["last_recommendation_query"] is None

    state = SessionState.model_validate(first_response.state)
    second_response = service.handle_message(
        user_message="How do you have my destination what do you mean",
        session_state=state,
        recent_messages=[
            TranscriptMessage(role="user", content="Hello Tommy"),
            TranscriptMessage(
                role="assistant",
                content=first_response.assistant_message,
            ),
        ],
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="Which destination should I focus on?")]
        },
    )

    assert "By destination" in second_response.assistant_message
    assert second_response.state["constraints"].get("destination") is None
    assert second_response.state["entities"]["destinations"] == []
    assert second_response.state["conversation"]["last_requested_slots"] == [
        "destination"
    ]
    assert second_response.state["conversation"]["last_user_intent"] == "clarify"
    assert (
        second_response.state["conversation"]["last_recommendation_item_type"] is None
    )
    assert second_response.state["conversation"]["last_recommendation_query"] is None


def test_orchestrator_reasks_same_missing_slot_until_it_is_captured() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-repeat-slot",
            "conversation": {
                "last_requested_slots": ["destination"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "recommend hotels with nightlife",
            },
        }
    )

    response = service.handle_message(
        user_message="I'm flexible",
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

    assert response.state["conversation"]["last_requested_slots"] == ["destination"]
    assert "destination" in response.assistant_message.casefold()
    assert response.state["conversation"]["last_recommendation_item_type"] == "hotel"


def test_orchestrator_final_slot_executes_recommendation_even_if_agent_clarifies() -> (
    None
):
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-final-slot",
            "constraints": {
                "destination": "Lisbon",
                "dates": {"start": "2026-06-10", "end": "2026-06-17"},
            },
            "conversation": {
                "last_requested_slots": ["budget"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "destination",
                "last_recommendation_query": "recommend a beach trip Lisbon",
            },
        }
    )
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
                        "item_id": "dest-lisbon-2",
                        "item_type": "destination",
                        "score": 0.91,
                        "rank": 1,
                        "features": {"name": "Lisbon Beach Escape"},
                        "explanation": "Fits the requested beach-city balance.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="under 1500 EUR",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant", content="What budget range should I use?"
            )
        ],
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="What budget range should I use?")]
        },
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.filters["item_type"] == "destination"
    assert query.constraints.destination == "Lisbon"
    assert query.constraints.budget is not None
    assert query.constraints.budget.max == 1500.0
    assert response.recommendations[0].item_id == "dest-lisbon-2"
    assert response.state["conversation"]["last_requested_slots"] == []
    assert response.state["status"] == "refine"


def test_orchestrator_uses_grounded_response_composer_after_tool_result() -> None:
    service = OrchestratorService()
    captured_prompts: list[str] = []

    response = service.handle_message(
        user_message="show me more",
        session_state=_base_state(),
        recent_messages=[
            TranscriptMessage(role="user", content="Find me a hotel in Lisbon"),
        ],
        agent_executor=lambda _messages: {
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
                AIMessage(content="Raw transcript copy that should not be returned."),
            ]
        },
        response_composer=lambda prompt: captured_prompts.append(prompt)
        or "Here is a more natural grounded hotel update.",
    )

    assert response.assistant_message == "Here is a more natural grounded hotel update."
    assert captured_prompts
    assert "Lisbon Stay" in captured_prompts[0]
    assert "Raw transcript copy" not in response.assistant_message


def test_orchestrator_multi_turn_slot_filling_reaches_recommendation_on_final_turn() -> (
    None
):
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
                        "item_id": "hotel-lisbon-3",
                        "item_type": "hotel",
                        "score": 0.9,
                        "rank": 1,
                        "features": {"name": "Lisbon Budget Stay"},
                        "explanation": "Grounded hotel option within the budget.",
                    }
                ],
            }
        )

    state = SessionState(session_id="sess-flow")

    response = service.handle_message(
        user_message="recommend hotels",
        session_state=state,
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="Which destination should I focus on?")]
        },
        recommendation_executor=recommendation_executor,
    )
    state = SessionState.model_validate(response.state)
    assert state.conversation.last_user_intent == "recommend"
    assert state.conversation.last_recommendation_item_type == "hotel"
    assert state.conversation.last_requested_slots == ["destination"]

    response = service.handle_message(
        user_message="Lisbon",
        session_state=state,
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="What travel dates should I plan around?")]
        },
        recommendation_executor=recommendation_executor,
    )
    state = SessionState.model_validate(response.state)
    assert state.constraints.destination == "Lisbon"
    assert state.conversation.last_requested_slots == ["dates"]

    response = service.handle_message(
        user_message="next weekend",
        session_state=state,
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="What budget range should I use?")]
        },
        recommendation_executor=recommendation_executor,
    )
    state = SessionState.model_validate(response.state)
    assert state.constraints.dates is not None
    assert state.conversation.last_requested_slots == ["budget"]

    response = service.handle_message(
        user_message="under 1500 EUR",
        session_state=state,
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="What budget range should I use?")]
        },
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.filters["item_type"] == "hotel"
    assert query.constraints.destination == "Lisbon"
    assert query.constraints.budget is not None
    assert query.constraints.budget.max == 1500.0
    assert response.recommendations[0].item_id == "hotel-lisbon-3"


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
