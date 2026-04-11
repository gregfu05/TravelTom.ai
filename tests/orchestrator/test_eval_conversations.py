"""Evaluation conversation scenarios for the orchestrator.

These tests are higher-level conversation checks intended to guard core UX flows:
- slot gating for hotel searches
- immediate tool execution for complete requests
- safe empty-results fallback (no hallucinated items)
- preference capture and carry-forward into subsequent queries

They follow the patterns used in tests/orchestrator/test_service.py.
"""

from __future__ import annotations

from app.schemas.state import SessionState
from app.schemas.tools.recommendations import RecommendationQuery, RecommendationToolResponse
from app.services.orchestrator.service import OrchestratorService
from langchain_core.messages import AIMessage


def test_eval_missing_core_slots_asks_for_destination_dates_budget_and_no_tool_call() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def recommendation_executor(query: RecommendationQuery) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {"ranking_version": "heuristic-v1", "results": []}
        )

    response = service.handle_message(
        user_message="show me hotels",
        session_state=SessionState(session_id="sess-eval-missing-slots"),
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    assert captured_query["value"] is None
    message = response.assistant_message.casefold()
    assert "destination" in message
    assert "date" in message
    assert "budget" in message


def test_eval_complete_request_calls_tool_immediately_and_no_clarification() -> None:
    service = OrchestratorService()
    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def recommendation_executor(query: RecommendationQuery) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {
                "ranking_version": "heuristic-v1",
                "results": [
                    {
                        "item_id": "hotel-sb-1",
                        "item_type": "hotel",
                        "score": 0.91,
                        "rank": 1,
                        "features": {"name": "Santa Barbara Hotel"},
                        "explanation": "Grounded hotel match.",
                    }
                ],
            }
        )

    response = service.handle_message(
        user_message="Santa Barbara May 10–20, 2000 EUR, hotels",
        session_state=SessionState(session_id="sess-eval-complete"),
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    assert captured_query["value"] is not None
    assert response.recommendations

    assistant = response.assistant_message.casefold()
    assert "destination" not in assistant
    assert "travel dates" not in assistant
    assert "budget" not in assistant


def test_eval_empty_results_fallback_no_hallucinations_and_suggests_adjustments() -> None:
    service = OrchestratorService()

    def recommendation_executor(_query: RecommendationQuery) -> RecommendationToolResponse:
        return RecommendationToolResponse.model_validate(
            {"ranking_version": "heuristic-v1", "results": []}
        )

    response = service.handle_message(
        user_message="Santa Barbara May 10-20, 2000 EUR, hotels",
        session_state=SessionState(session_id="sess-eval-empty-results"),
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    assert response.recommendations == []

    msg = response.assistant_message.casefold()
    # Should not present fabricated recommendations.
    assert "top picks" not in msg
    assert "1." not in msg

    # Should guide the user to adjust constraints/preferences.
    assert any(
        token in msg
        for token in (
            "adjust",
            "broaden",
            "widen",
            "different",
            "lower",
            "higher",
            "budget",
            "dates",
        )
    )


def test_eval_personalization_follow_up_query_includes_interests() -> None:
    service = OrchestratorService()
    state = SessionState(session_id="sess-eval-personalization")

    first = service.handle_message(
        user_message="I like nightlife and food",
        session_state=state,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
    )

    next_state = SessionState.model_validate(first.state)

    captured_query: dict[str, RecommendationQuery | None] = {"value": None}

    def recommendation_executor(query: RecommendationQuery) -> RecommendationToolResponse:
        captured_query["value"] = query
        return RecommendationToolResponse.model_validate(
            {"ranking_version": "heuristic-v1", "results": []}
        )

    service.handle_message(
        user_message="show me options",
        session_state=next_state,
        agent_executor=lambda _messages: {"messages": [AIMessage(content="ignored")]},
        recommendation_executor=recommendation_executor,
    )

    query = captured_query["value"]
    assert query is not None

    normalized_query = query.query.casefold()
    assert "nightlife" in normalized_query
    assert "food" in normalized_query
