"""Scripted evaluation conversations for the TravelTom agent.

These are lightweight, deterministic multi-turn tests that measure:
- progressive clarification (ask when core info is missing)
- non-hallucination (never invent results when tool returns empty)
- personalization (carry and use weighted_interests)

They are intentionally property-based (assert on behavior), not exact phrasing.
"""

from __future__ import annotations

from typing import Any, Callable

from app.schemas.orchestrator import TranscriptMessage
from app.schemas.state import SessionState
from app.schemas.tools.recommendations import RecommendationQuery, RecommendationToolResponse
from app.services.orchestrator.service import OrchestratorService


RecommendationExecutor = Callable[[RecommendationQuery], RecommendationToolResponse]


def _fake_recommendation_executor_factory(*, results_for_item_type: dict[str, list[dict[str, Any]]]):
    """Return a deterministic tool executor that records the last query."""

    captured: dict[str, Any] = {"last_query": None}

    def executor(query: RecommendationQuery) -> RecommendationToolResponse:
        captured["last_query"] = query
        results = results_for_item_type.get(str(query.filters.get("item_type") or "destination"), [])
        payload = {"ranking_version": query.ranking_version, "results": results}
        return RecommendationToolResponse.model_validate(payload)

    return executor, captured


def _run_conversation(
    *,
    service: OrchestratorService,
    session_state: SessionState,
    turns: list[str],
    recommendation_executor: RecommendationExecutor | None = None,
) -> tuple[SessionState, list[str]]:
    """Replay a list of user turns, returning final state and assistant messages."""

    assistant_messages: list[str] = []
    transcript: list[TranscriptMessage] = []
    state = session_state

    for user_message in turns:
        response = service.handle_message(
            user_message=user_message,
            session_state=state,
            recent_messages=list(transcript),
            agent_executor=lambda _messages: {"messages": []},
            planner_executor=None,
            recommendation_executor=recommendation_executor,
        )
        assistant_messages.append(response.assistant_message)
        state = SessionState.model_validate(response.state)
        transcript.append(TranscriptMessage(role="user", content=user_message))
        transcript.append(TranscriptMessage(role="assistant", content=response.assistant_message))

    return state, assistant_messages


def test_eval_progressive_clarification_for_hotels_missing_core_slots() -> None:
    service = OrchestratorService()

    state, assistant_messages = _run_conversation(
        service=service,
        session_state=SessionState(session_id="eval-clarify-hotels"),
        turns=[
            "I want hotels",
            "Lisbon",
            "June 10th to June 17th",
            "2000 euros",
            "hotels",
        ],
        recommendation_executor=(
            _fake_recommendation_executor_factory(
                results_for_item_type={
                    "hotel": [
                        {
                            "item_id": "hotel-1",
                            "item_type": "hotel",
                            "score": 0.9,
                            "rank": 1,
                            "features": {"name": "Hotel One"},
                            "explanation": "Matches your constraints.",
                        }
                    ]
                }
            )[0]
        ),
    )

    # The agent should progressively ask for the missing slots; by the end, it should
    # have destination/dates/budget and be in refine mode with results.
    assert any("destination" in msg.casefold() for msg in assistant_messages[:2])
    assert any("date" in msg.casefold() for msg in assistant_messages[:3])
    assert any("budget" in msg.casefold() for msg in assistant_messages[:4])

    assert state.constraints.destination == "Lisbon"
    assert state.constraints.dates is not None
    assert state.constraints.budget is not None
    assert state.conversation.last_recommendation_item_type == "hotel"
    assert state.status == "refine"


def test_eval_no_hallucinations_when_tool_returns_empty_results() -> None:
    service = OrchestratorService()

    executor, captured = _fake_recommendation_executor_factory(results_for_item_type={"hotel": []})

    state, assistant_messages = _run_conversation(
        service=service,
        session_state=SessionState.model_validate(
            {
                "session_id": "eval-empty-results",
                "constraints": {
                    "destination": "Santa Barbara",
                    "dates": {"start": "2026-05-10", "end": "2026-05-20"},
                    "budget": {"min": 0, "max": 2000, "currency": "EUR"},
                },
                "conversation": {
                    "last_user_intent": "recommend",
                    "last_recommendation_item_type": "hotel",
                },
            }
        ),
        turns=["Find me hotels"],
        recommendation_executor=executor,
    )

    # Tool was called.
    assert captured["last_query"] is not None
    # Agent should not invent named options; it should acknowledge no matches and ask to adjust.
    msg = assistant_messages[-1].casefold()
    assert "not" in msg and ("match" in msg or "strong" in msg)
    assert "guess" not in msg  # shouldn't claim guessing; should state lack of results
    assert state.conversation.last_search_outcome == "empty_results"


def test_eval_personalization_interests_are_carried_into_follow_up_query() -> None:
    service = OrchestratorService()

    executor, captured = _fake_recommendation_executor_factory(
        results_for_item_type={
            "destination": [
                {
                    "item_id": "dest-1",
                    "item_type": "destination",
                    "score": 0.8,
                    "rank": 1,
                    "features": {"name": "Example Place"},
                    "explanation": "Nightlife and food scene.",
                }
            ]
        }
    )

    state = SessionState(session_id="eval-interests")
    state.preferences.weighted_interests = {"nightlife": 0.8, "food": 0.8}
    state.conversation.last_user_intent = "recommend"
    state.conversation.last_recommendation_item_type = "destination"
    state.conversation.last_recommendation_query = "destination ideas"

    _final_state, _assistant_messages = _run_conversation(
        service=service,
        session_state=state,
        turns=["show me more"],
        recommendation_executor=executor,
    )

    query = captured["last_query"]
    assert query is not None
    # Query text should carry forward prior context + top interests.
    assert "nightlife" in query.query.casefold()
    assert "food" in query.query.casefold()
