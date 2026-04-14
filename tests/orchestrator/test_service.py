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

    def planner_executor(prompt: str) -> dict[str, Any]:
        captured_prompt["value"] = prompt
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {
                "query": "calm scenic destinations",
                "filters": {"item_type": "destination"},
            },
        }

    service.handle_message(
        user_message="I want something calm and scenic, not sure where yet",
        session_state=SessionState(session_id="sess-planner-prompt"),
        recent_messages=[
            TranscriptMessage(role="user", content="I want a relaxing trip."),
            TranscriptMessage(role="assistant", content="Here are grounded options."),
        ],
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="Need more detail")]
        },
    )

    assert (
        "Latest user message: I want something calm and scenic, not sure where yet"
        in captured_prompt["value"]
    )
    assert "user: I want a relaxing trip." in captured_prompt["value"]
    assert "assistant: Here are grounded options." in captured_prompt["value"]
    assert (
        '"effective_query":"I want something calm and scenic, not sure where yet"'
        in captured_prompt["value"]
    )


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
        user_message="I want something calm and scenic, not sure where yet",
        session_state=SessionState(session_id="sess-planner-truncate"),
        recent_messages=[
            TranscriptMessage(role="assistant", content=long_assistant_message),
        ],
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="Need more detail")]
        },
        recommendation_executor=None,
    )

    assert response.assistant_message
    assert response.recommendations == []
    assert long_assistant_message not in captured_prompt["value"]
    assert "assistant: Top picks:" in captured_prompt["value"]
    assert "..." in captured_prompt["value"]


def test_orchestrator_greeting_uses_planner_when_available() -> None:
    service = OrchestratorService()
    planner_called = {"value": False}

    def planner_executor(_prompt: str) -> dict[str, Any]:
        planner_called["value"] = True
        return {
            "intent": "clarify",
            "should_call_recommendation_tool": False,
            "clarification_message": (
                "Hi, I'm Tom. Tell me where you want to go, or share destination, "
                "dates, and budget and I'll turn that into grounded recommendations."
            ),
        }

    response = service.handle_message(
        user_message="Hello Tommy",
        session_state=SessionState(session_id="sess-greeting-planner"),
        planner_executor=planner_executor,
        agent_executor=lambda _messages: (_ for _ in ()).throw(
            AssertionError("planner clarification should bypass the agent")
        ),
    )

    assert planner_called["value"] is True
    assert response.assistant_message.startswith("Hi, I'm Tom.")
    assert response.state["constraints"].get("destination") is None
    assert response.state["entities"]["destinations"] == []


def test_orchestrator_planner_patch_updates_state_before_clarification() -> None:
    service = OrchestratorService()
    state = SessionState(session_id="sess-planner-slot")

    response = service.handle_message(
        user_message="We can base this around Kyoto",
        session_state=state,
        planner_executor=lambda _prompt: {
            "intent": "recommend",
            "should_call_recommendation_tool": False,
            "clarification_message": "What travel dates should I plan around?",
            "state_patch": {"constraints": {"destination": "Kyoto"}},
            "query_controls": {"filters": {"item_type": "hotel"}},
        },
        agent_executor=lambda _messages: (_ for _ in ()).throw(
            AssertionError("planner clarification should bypass the agent")
        ),
    )

    assert response.state["constraints"]["destination"] == "Kyoto"
    assert response.state["conversation"]["last_requested_slots"] == ["dates"]
    assert response.state["conversation"]["last_user_intent"] == "recommend"
    assert "travel dates" in response.assistant_message
    assert response.state["conversation"]["last_user_intent"] == "recommend"
    assert "travel dates" in response.assistant_message


def test_orchestrator_state_patch_conversation_does_not_block_recommendation() -> None:
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
                        "features": {"name": "Lisbon Harbor Hotel"},
                        "explanation": "Planner output validated and reached tool.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="show me hotels",
        session_state=_base_state(),
        planner_executor=lambda _prompt: {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {"conversation": {"last_clarification_kind": "greeting"}},
            "query_controls": {
                "filters": {"item_type": "hotel"},
                "max_results": 3,
            },
        },
        agent_executor=lambda _messages: {"messages": [AIMessage(content="Checking")]},
        recommendation_executor=recommendation_executor,
    )

    assert captured_query["value"] is not None
    query = captured_query["value"]
    assert query is not None
    assert query.filters.get("item_type") == "hotel"
    assert query.max_results == 3
    assert response.recommendations
    assert response.recommendations[0].features.get("name") == "Lisbon Harbor Hotel"


def test_orchestrator_nested_state_patch_query_controls_reaches_recommendation() -> (
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
                        "item_id": "hotel-kyoto-1",
                        "item_type": "hotel",
                        "score": 0.93,
                        "rank": 1,
                        "features": {"name": "Kyoto Planner Hotel"},
                        "explanation": (
                            "Planner nested query_controls mapped correctly."
                        ),
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="show me hotel options",
        session_state=_base_state(),
        planner_executor=lambda _prompt: {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {
                "query_controls": {
                    "filters": {"item_type": "hotel"},
                    "max_results": 3,
                }
            },
        },
        agent_executor=lambda _messages: {"messages": [AIMessage(content="Checking")]},
        recommendation_executor=recommendation_executor,
    )

    assert captured_query["value"] is not None
    query = captured_query["value"]
    assert query is not None
    assert query.filters.get("item_type") == "hotel"
    assert query.max_results == 3
    assert response.recommendations
    assert response.recommendations[0].features.get("name") == "Kyoto Planner Hotel"


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
        return {
            "messages": [AIMessage(content="What travel dates should I plan around?")]
        }

    response = service.handle_message(
        user_message="Lisbon",
        session_state=state,
        planner_executor=lambda _prompt: {
            "intent": "recommend",
            "should_call_recommendation_tool": False,
            "state_patch": {
                "constraints": {"budget": {"min": 1000, "max": 10, "currency": "USD"}}
            },
        },
        agent_executor=agent_executor,
    )

    assert "value" not in captured_messages
    assert response.state["constraints"]["destination"] == "Lisbon"
    assert response.state["conversation"]["last_requested_slots"] == ["dates"]
    assert "travel dates" in response.assistant_message


def test_orchestrator_logs_planner_failure_and_falls_back_safely(caplog: Any) -> None:
    service = OrchestratorService()
    state = SessionState(session_id="sess-planner-failure")

    def planner_executor(_prompt: str) -> dict[str, Any]:
        raise PlannerExecutionError("planner transport failed")

    with caplog.at_level("WARNING"):
        response = service.handle_message(
            user_message="I want something calm and scenic, not sure where yet",
            session_state=state,
            planner_executor=planner_executor,
            agent_executor=lambda _messages: {
                "messages": [
                    AIMessage(content="What travel dates should I plan around?")
                ]
            },
        )

    assert response.assistant_message
    assert any(
        record.message == "planner_execution_failed" for record in caplog.records
    )


def test_orchestrator_follow_up_refine_uses_planner_when_available() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}
    planner_called = {"value": False}

    def planner_executor(_prompt: str) -> dict[str, Any]:
        planner_called["value"] = True
        return {
            "intent": "refine",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {
                "query": "show me more hotel Lisbon nightlife",
                "filters": {"item_type": "hotel"},
            },
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
                        "item_id": "dest-quiet-2",
                        "item_type": "destination",
                        "score": 0.91,
                        "rank": 1,
                        "features": {"name": "Planner Override Destination"},
                        "explanation": "Planner query controls shaped the fallback.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="show me more",
        session_state=_base_state(),
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="Tell me more")]
        },
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert planner_called["value"] is True
    assert query.query == "show me more hotel Lisbon nightlife"
    assert query.filters["item_type"] == "hotel"
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
        "Based on your interests in nightlife, I found 1 places that fit your request."
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
    assert query is None
    assert response.state["conversation"]["last_recommendation_item_type"] == "flight"
    assert response.state["conversation"]["last_requested_slots"] == ["origin"]
    assert "flying from" in response.assistant_message.casefold()


def test_orchestrator_generic_trip_flow_asks_for_search_type_after_budget() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-generic-trip",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
            },
            "conversation": {
                "last_requested_slots": ["budget"],
                "last_user_intent": "recommend",
                "last_recommendation_query": ("Santa Barbara 10th May to 20th May"),
            },
        }
    )

    response = service.handle_message(
        user_message="2000 euros",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant",
                content="What budget range should I use?",
            )
        ],
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
    )

    assert response.state["constraints"]["budget"] == {
        "min": 0.0,
        "max": 2000.0,
        "currency": "EUR",
    }
    assert response.state["conversation"]["last_user_intent"] == "recommend"
    assert response.state["conversation"]["last_clarification_kind"] == "search_type"
    assert response.state["conversation"]["last_recommendation_item_type"] is None
    assert response.state["conversation"]["last_requested_slots"] == []
    assert "hotel recommendations or flights" in response.assistant_message


def test_orchestrator_one_shot_trip_message_asks_for_search_type() -> None:
    service = OrchestratorService()

    response = service.handle_message(
        user_message="Santa Barbara 10th May to 20th May 2000 euros",
        session_state=SessionState(session_id="sess-one-shot-search-type"),
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
    )

    assert response.state["constraints"]["destination"] == "Santa Barbara"
    assert response.state["constraints"]["dates"] == {
        "start": "2026-05-10",
        "end": "2026-05-20",
    }
    assert response.state["constraints"]["budget"] == {
        "min": 0.0,
        "max": 2000.0,
        "currency": "EUR",
    }
    assert response.state["conversation"]["last_user_intent"] == "recommend"
    assert response.state["conversation"]["last_clarification_kind"] == "search_type"
    assert "hotel recommendations or flights" in response.assistant_message


def test_orchestrator_search_type_reply_uses_planner_when_available() -> None:
    service = OrchestratorService()
    planner_called = {"value": False}
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}
    state = SessionState.model_validate(
        {
            "session_id": "sess-search-type-planner",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
                "budget": {"min": 0, "max": 2000, "currency": "EUR"},
            },
            "conversation": {
                "last_user_intent": "recommend",
                "last_clarification_kind": "search_type",
                "last_recommendation_query": (
                    "Santa Barbara 10th May to 20th May 2000 euros"
                ),
            },
        }
    )

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "hotel-sb-planner",
                        "item_type": "hotel",
                        "score": 0.94,
                        "rank": 1,
                        "features": {"name": "Planner Hotel"},
                        "explanation": "Planner-selected hotel search.",
                    }
                ],
            }
        )

    def planner_executor(_prompt: str) -> dict[str, Any]:
        planner_called["value"] = True
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "state_patch": {},
            "query_controls": {
                "query": "hotel Santa Barbara 10th May to 20th May 2000 euros",
                "filters": {"item_type": "hotel"},
            },
        }

    response = service.handle_message(
        user_message="I want hotels to be honest",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant",
                content=(
                    "I have your destination, dates, and budget. Should I look for "
                    "hotel recommendations or flights?"
                ),
            )
        ],
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert planner_called["value"] is True
    assert query is not None
    assert query.constraints.destination == "Santa Barbara"
    assert query.filters["item_type"] == "hotel"
    assert response.recommendations[0].item_type == "hotel"
    assert response.state["conversation"]["last_recommendation_item_type"] == "hotel"


def test_orchestrator_vague_search_type_defaults_to_hotels() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}
    state = SessionState.model_validate(
        {
            "session_id": "sess-search-type-default-hotel",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
                "budget": {"min": 0, "max": 2000, "currency": "EUR"},
            },
            "conversation": {
                "last_user_intent": "recommend",
                "last_clarification_kind": "search_type",
                "last_recommendation_query": (
                    "Santa Barbara 10th May to 20th May 2000 euros"
                ),
            },
        }
    )

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "hotel-sb-default",
                        "item_type": "hotel",
                        "score": 0.9,
                        "rank": 1,
                        "features": {"name": "Default Hotel"},
                        "explanation": "Falls back to hotels for a fixed destination.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="Anything works",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant",
                content=(
                    "I have your destination, dates, and budget. Should I look for "
                    "hotel recommendations or flights?"
                ),
            )
        ],
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.filters["item_type"] == "hotel"
    assert "Santa Barbara 10th May to 20th May 2000 euros" in query.query
    assert response.state["conversation"]["last_recommendation_item_type"] == "hotel"
    assert response.recommendations[0].item_type == "hotel"


def test_orchestrator_planner_first_trip_flow_reaches_hotel_recommendation() -> None:
    service = OrchestratorService()
    planner_calls = {"count": 0}
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def planner_executor(prompt: str) -> dict[str, Any]:
        planner_calls["count"] += 1
        if "Latest user message: I want to go to Santa Barbara" in prompt:
            return {
                "intent": "recommend",
                "should_call_recommendation_tool": False,
                "clarification_message": "What travel dates should I plan around?",
                "state_patch": {"constraints": {"destination": "Santa Barbara"}},
            }
        if "Latest user message: Let's say May 10th to May 20th" in prompt:
            return {
                "intent": "recommend",
                "should_call_recommendation_tool": False,
                "clarification_message": "What budget range should I use?",
                "state_patch": {
                    "constraints": {
                        "dates": {"start": "2026-05-10", "end": "2026-05-20"}
                    }
                },
            }
        if "Latest user message: 2000 euros" in prompt:
            return {
                "intent": "recommend",
                "should_call_recommendation_tool": False,
                "clarification_message": (
                    "Should I look for hotel recommendations or flights?"
                ),
                "state_patch": {
                    "constraints": {
                        "budget": {"min": 0, "max": 2000, "currency": "EUR"}
                    }
                },
            }
        if "Latest user message: I want hotels to be honest" in prompt:
            return {
                "intent": "recommend",
                "should_call_recommendation_tool": True,
                "state_patch": {},
                "query_controls": {
                    "query": "hotel Santa Barbara 10th May to 20th May 2000 euros",
                    "filters": {"item_type": "hotel"},
                },
            }
        raise AssertionError(f"Unexpected prompt: {prompt}")

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "hotel-sb-flow",
                        "item_type": "hotel",
                        "score": 0.97,
                        "rank": 1,
                        "features": {"name": "Flow Hotel"},
                        "explanation": "Grounded hotel for the planner-first flow.",
                    }
                ],
            }
        )

    state = SessionState(session_id="sess-planner-trip-flow")

    response = service.handle_message(
        user_message="I want to go to Santa Barbara",
        session_state=state,
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )
    state = SessionState.model_validate(response.state)
    assert state.constraints.destination == "Santa Barbara"

    response = service.handle_message(
        user_message="Let's say May 10th to May 20th",
        session_state=state,
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )
    state = SessionState.model_validate(response.state)
    assert state.constraints.dates is not None

    response = service.handle_message(
        user_message="2000 euros",
        session_state=state,
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )
    state = SessionState.model_validate(response.state)
    assert state.constraints.budget is not None
    assert state.conversation.last_clarification_kind == "search_type"

    response = service.handle_message(
        user_message="I want hotels to be honest",
        session_state=state,
        planner_executor=planner_executor,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert planner_calls["count"] == 4
    assert query is not None
    assert query.constraints.destination == "Santa Barbara"
    assert query.filters["item_type"] == "hotel"
    assert response.recommendations[0].item_id == "hotel-sb-flow"
    assert response.state["conversation"]["last_recommendation_item_type"] == "hotel"
    assert response.state["constraints"]["destination"] == "Santa Barbara"


def test_orchestrator_planner_search_type_reply_bypasses_agent_when_ready() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}
    planner_called = {"value": False}
    state = SessionState.model_validate(
        {
            "session_id": "sess-search-type-bypass",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
                "budget": {"min": 0, "max": 2000, "currency": "EUR"},
            },
            "conversation": {
                "last_user_intent": "recommend",
                "last_clarification_kind": "search_type",
            },
            "status": "explore",
        }
    )

    def recommendation_executor(
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "hotel-sb-bypass",
                        "item_type": "hotel",
                        "score": 0.95,
                        "rank": 1,
                        "features": {"name": "Planner Bypass Hotel"},
                        "explanation": (
                            "Grounded hotel returned without chat-agent lag."
                        ),
                    }
                ],
            }
        )

    def planner_executor(_prompt: str) -> dict[str, Any]:
        planner_called["value"] = True
        return {
            "intent": "recommend",
            "should_call_recommendation_tool": True,
            "clarification_message": None,
            "state_patch": {},
            "query_controls": {
                "query": "hotel Santa Barbara 10th May to 20th May 2000 euros",
                "filters": {"item_type": "hotel"},
            },
        }

    response = service.handle_message(
        user_message="I want hotels to be honest",
        session_state=state,
        planner_executor=planner_executor,
        agent_executor=lambda _messages: (_ for _ in ()).throw(
            AssertionError("agent should be bypassed")
        ),
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert planner_called["value"] is True
    assert query is not None
    assert query.filters["item_type"] == "hotel"
    assert query.constraints.destination == "Santa Barbara"
    assert response.recommendations[0].item_id == "hotel-sb-bypass"
    assert response.state["conversation"]["last_recommendation_item_type"] == "hotel"


def test_orchestrator_lower_cost_keeps_hotel_context_when_planner_clarifies() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-lower-cost-context",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
                "budget": {"min": 0, "max": 2000, "currency": "EUR"},
            },
            "conversation": {
                "last_user_intent": "refine",
                "last_search_outcome": "results",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": (
                    "hotel Santa Barbara 10th May to 20th May 2000 euros"
                ),
                "last_recommendation_result_ids": ["hotel-sb-1"],
            },
            "status": "refine",
        }
    )

    response = service.handle_message(
        user_message="lower cost",
        session_state=state,
        planner_executor=lambda _prompt: {
            "intent": "refine",
            "should_call_recommendation_tool": False,
            "clarification_message": (
                "What budget cap should I target for lower-cost hotel options?"
            ),
            "state_patch": {},
            "query_controls": {
                "query": (
                    "lower cost hotel Santa Barbara 10th May to 20th May 2000 euros"
                ),
                "filters": {"item_type": "hotel"},
            },
        },
        agent_executor=lambda _messages: {
            "messages": [
                AIMessage(
                    content=(
                        "What budget cap should I target for lower-cost hotel "
                        "options?"
                    )
                )
            ]
        },
    )

    assert response.assistant_message == (
        "What budget cap should I target for lower-cost hotel options?"
    )
    assert response.state["constraints"]["destination"] == "Santa Barbara"
    assert response.state["conversation"]["last_recommendation_item_type"] == "hotel"
    assert (
        "lower cost hotel Santa Barbara"
        in response.state["conversation"]["last_recommendation_query"]
    )


def test_orchestrator_search_type_reply_for_flights_asks_for_origin() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-search-type-flight",
            "constraints": {
                "destination": "Lisbon",
                "dates": {"start": "2026-04-04", "end": "2026-04-05"},
                "budget": {"min": 0, "max": 500, "currency": "EUR"},
            },
            "conversation": {
                "last_user_intent": "recommend",
                "last_clarification_kind": "search_type",
                "last_recommendation_query": "Lisbon next weekend 500 euros",
            },
        }
    )

    response = service.handle_message(
        user_message="flights",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant",
                content=(
                    "I have your destination, dates, and budget. Should I look for "
                    "hotel recommendations or flights?"
                ),
            )
        ],
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
    )

    assert response.state["conversation"]["last_recommendation_item_type"] == "flight"
    assert response.state["conversation"]["last_requested_slots"] == ["origin"]
    assert response.state["conversation"]["last_clarification_kind"] == "core_slot"
    assert "flying from" in response.assistant_message.casefold()


def test_orchestrator_vague_reply_after_empty_results_gives_stronger_guidance() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-empty-follow-up",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
                "budget": {"min": 0, "max": 2000, "currency": "EUR"},
            },
            "conversation": {
                "last_user_intent": "refine",
                "last_clarification_kind": "refine_preference",
                "last_search_outcome": "empty_results",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": (
                    "hotel Santa Barbara 10th May to 20th May 2000 euros"
                ),
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
                "results": [],
            }
        )

    response = service.handle_message(
        user_message="Anything works",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant",
                content=(
                    "I am not seeing strong matches with those constraints yet. "
                    "I can help narrow this down. Tell me what you want to optimize "
                    "for, like lower cost, fewer layovers, or a different vibe."
                ),
            )
        ],
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    assert captured_query["value"] is None
    assert "still do not have grounded hotel matches" in response.assistant_message
    assert (
        response.state["conversation"]["last_clarification_kind"] == "refine_preference"
    )
    assert response.state["conversation"]["last_search_outcome"] == "empty_results"


def test_orchestrator_flight_route_reply_captures_origin_and_destination() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-flight-route",
            "conversation": {
                "last_requested_slots": ["origin", "destination"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "flight",
                "last_recommendation_query": "recommend flights",
            },
        }
    )

    response = service.handle_message(
        user_message="Madrid to Lisbon",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant",
                content="Where are you flying from and where do you want to go?",
            )
        ],
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
    )

    assert response.state["constraints"]["origin"] == "Madrid"
    assert response.state["constraints"]["destination"] == "Lisbon"
    assert response.state["conversation"]["last_requested_slots"] == ["dates"]
    assert "travel dates" in response.assistant_message.casefold()


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


def test_orchestrator_day_first_dates_fill_advances_past_dates_slot() -> None:
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-day-first-loop",
            "constraints": {"destination": "Santa Barbara"},
            "conversation": {
                "last_requested_slots": ["dates"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "recommend hotels",
            },
        }
    )

    response = service.handle_message(
        user_message="Let's go for something like 10th of May to 20th of May",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant",
                content=(
                    "What travel dates should I use for these hotel " "recommendations?"
                ),
            )
        ],
        agent_executor=lambda _messages: {
            "messages": [AIMessage(content="What budget range should I use?")]
        },
    )

    assert response.state["constraints"]["dates"] == {
        "start": "2026-05-10",
        "end": "2026-05-20",
    }
    assert response.state["constraints"]["destination"] == "Santa Barbara"
    assert response.state["conversation"]["last_requested_slots"] == ["budget"]
    assert "budget" in response.assistant_message.casefold()


def test_orchestrator_bare_budget_reply_executes_recommendation_after_budget_slot() -> (
    None
):
    service = OrchestratorService()
    state = SessionState.model_validate(
        {
            "session_id": "sess-budget-bare-reply",
            "constraints": {
                "destination": "Santa Barbara",
                "dates": {"start": "2026-05-10", "end": "2026-05-20"},
            },
            "conversation": {
                "last_requested_slots": ["budget"],
                "last_user_intent": "recommend",
                "last_recommendation_item_type": "hotel",
                "last_recommendation_query": "recommend hotels",
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
                        "item_id": "hotel-sb-1",
                        "item_type": "hotel",
                        "score": 0.95,
                        "rank": 1,
                        "features": {"name": "Budget Reply Hotel"},
                        "explanation": "Grounded hotel within the requested budget.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="2000 euros",
        session_state=state,
        recent_messages=[
            TranscriptMessage(
                role="assistant",
                content=(
                    "What budget range should I use for these hotel " "recommendations?"
                ),
            )
        ],
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None
    assert query.constraints.budget is not None
    assert query.constraints.budget.max == 2000.0
    assert query.constraints.budget.currency == "EUR"
    assert response.recommendations[0].item_id == "hotel-sb-1"
    assert response.state["conversation"]["last_requested_slots"] == []


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

    assert first_response.assistant_message.startswith("Hi, I'm Tom.")
    assert first_response.state["constraints"].get("destination") is None
    assert first_response.state["entities"]["destinations"] == []
    assert first_response.state["conversation"]["last_requested_slots"] == []
    assert first_response.state["conversation"]["last_user_intent"] == "clarify"
    assert first_response.state["conversation"]["last_recommendation_item_type"] is None
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

    def response_composer(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "Here is a more natural grounded hotel update."

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
        response_composer=response_composer,
    )

    assert response.assistant_message == "Here is a more natural grounded hotel update."
    assert captured_prompts
    assert "Lisbon Stay" in captured_prompts[0]
    assert "Raw transcript copy" not in response.assistant_message


def test_orchestrator_slot_filling_reaches_recommendation_on_final_turn() -> None:
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

    assert "Top picks:\n1. dest-lisbon" in message


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
