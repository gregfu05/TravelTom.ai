"""Tool-first orchestration service with strict schema validation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationConstraints,
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)
from app.services.orchestrator.langchain_compat import (
    LANGCHAIN_AVAILABLE,
    create_runnable_lambda,
    create_structured_tool,
)
from app.services.orchestrator.policies import (
    OrchestratorPolicyConfig,
    decide_next_action,
    missing_core_constraints,
)

RecommendationTool = Callable[
    [RecommendationQuery],
    RecommendationToolResponse | dict[str, Any],
]


def placeholder_recommendation_tool(
    query: RecommendationQuery,
) -> RecommendationToolResponse:
    """Temporary recommendation tool used until recommender integration is ready."""

    return RecommendationToolResponse(
        results=[],
        ranking_version=query.ranking_version,
    )


class OrchestratorResponse(BaseModel):
    """Normalized orchestrator output for API layer integration."""

    session_id: str
    assistant_message: str
    recommendations: list[RecommendationResult] = Field(default_factory=list)
    itinerary: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any]


class OrchestratorService:
    """Coordinates deterministic policy checks and LangChain tool execution."""

    def __init__(
        self,
        recommendation_tool: RecommendationTool | None = None,
        policy_config: OrchestratorPolicyConfig | None = None,
    ) -> None:
        self._recommendation_handler = (
            recommendation_tool or placeholder_recommendation_tool
        )
        self._policy = policy_config or OrchestratorPolicyConfig()
        self._uses_langchain = LANGCHAIN_AVAILABLE
        self._recommendation_structured_tool = create_structured_tool(
            func=self._recommendation_tool_adapter,
            name="recommendation_query",
            description="Run deterministic TravelTom recommendation retrieval.",
            args_schema=RecommendationQuery,
        )
        self._recommendation_chain = create_runnable_lambda(
            self._invoke_recommendation_chain
        )

    @property
    def uses_langchain(self) -> bool:
        """Return whether langchain_core runtime is available."""

        return self._uses_langchain

    def handle_message(
        self,
        *,
        user_message: str,
        session_state: SessionState,
    ) -> OrchestratorResponse:
        """Run deterministic orchestration for a single user message."""

        message = user_message.strip()
        if not message:
            return self._clarification_response(
                session_state=session_state,
                assistant_message=(
                    "Tell me where and when you want to travel, plus your budget, "
                    "and I can suggest options."
                ),
            )

        decision = decide_next_action(message, session_state)
        if not decision.should_call_recommendation_tool:
            return self._clarification_response(
                session_state=session_state,
                assistant_message=self._build_clarification_message(session_state),
            )

        query = self._build_recommendation_query(
            user_message=message,
            session_state=session_state,
        )
        if query is None:
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=(
                    "I could not validate your request yet. Please share destination, "
                    "dates, and budget so I can continue."
                ),
            )

        try:
            recommendation_response = self._recommendation_chain.invoke(query)
        except FuturesTimeoutError:
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=(
                    "I could not finish the recommendation lookup in time. "
                    "Please try again in a moment."
                ),
            )
        except ValidationError:
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=(
                    "I received an invalid recommendation payload. Please retry and "
                    "I will fetch results again."
                ),
            )
        except Exception:
            return self._safe_error_response(
                session_state=session_state,
                assistant_message=(
                    "I hit a temporary tool error. Please retry and I will continue "
                    "from this plan."
                ),
            )
        next_state = session_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.last_recommendation_version = recommendation_response.ranking_version

        if not recommendation_response.results:
            next_state.status = "explore"
            return OrchestratorResponse(
                session_id=next_state.session_id,
                assistant_message=(
                    "I do not have strong matches yet. "
                    f"{self._build_clarification_message(next_state)}"
                ),
                recommendations=[],
                itinerary=next_state.itinerary.model_dump(),
                state=next_state.model_dump(mode="json"),
            )

        next_state.status = "refine"
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=self._build_results_message(
                recommendation_response.results
            ),
            recommendations=recommendation_response.results,
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )

    def _build_recommendation_query(
        self,
        *,
        user_message: str,
        session_state: SessionState,
    ) -> RecommendationQuery | None:
        payload: dict[str, Any] = {
            "session_id": session_state.session_id,
            "query": user_message,
            "constraints": self._build_constraints_payload(session_state),
            "max_results": self._policy.max_recommendation_results,
            "ranking_version": "heuristic-v1",
        }
        try:
            return RecommendationQuery.model_validate(payload)
        except ValidationError:
            return None

    def _build_constraints_payload(self, session_state: SessionState) -> dict[str, Any]:
        constraints: dict[str, Any] = {}
        if session_state.constraints.origin:
            constraints["origin"] = session_state.constraints.origin
        if session_state.constraints.destination:
            constraints["destination"] = session_state.constraints.destination
        if session_state.constraints.dates:
            constraints["dates"] = session_state.constraints.dates.model_dump(
                mode="json"
            )
        if session_state.constraints.budget:
            constraints["budget"] = session_state.constraints.budget.model_dump(
                mode="json"
            )
        if session_state.constraints.party_size:
            constraints["party_size"] = (
                session_state.constraints.party_size.model_dump()
            )
        return constraints

    def _call_recommendation_tool(
        self,
        query: RecommendationQuery,
    ) -> RecommendationToolResponse | dict[str, Any]:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._recommendation_handler, query)
            return future.result(timeout=self._policy.recommendation_timeout_seconds)

    def _invoke_recommendation_chain(
        self,
        query: RecommendationQuery,
    ) -> RecommendationToolResponse:
        payload = query.model_dump(mode="python")
        tool_output = self._recommendation_structured_tool.invoke(payload)
        return RecommendationToolResponse.model_validate(tool_output)

    def _recommendation_tool_adapter(
        self,
        session_id: str,
        query: str,
        constraints: RecommendationConstraints | None = None,
        filters: dict[str, Any] | None = None,
        max_results: int = 20,
        ranking_version: str = "heuristic-v1",
    ) -> dict[str, Any]:
        recommendation_query = RecommendationQuery.model_validate(
            {
                "session_id": session_id,
                "query": query,
                "constraints": constraints or RecommendationConstraints(),
                "filters": filters or {},
                "max_results": max_results,
                "ranking_version": ranking_version,
            }
        )
        tool_output = self._call_recommendation_tool(recommendation_query)
        validated_output = RecommendationToolResponse.model_validate(tool_output)
        return validated_output.model_dump(mode="json")

    def _build_clarification_message(self, session_state: SessionState) -> str:
        missing = missing_core_constraints(session_state)
        if not missing:
            return (
                "Tell me what to optimize for, like cheaper options or fewer layovers."
            )
        if len(missing) == 1:
            return f"Please share your {missing[0]} so I can suggest options."
        joined = ", ".join(missing[:-1]) + f", and {missing[-1]}"
        return f"Please share your {joined} so I can suggest options."

    def _build_results_message(
        self,
        results: list[RecommendationResult],
    ) -> str:
        preview_items = ", ".join(
            f"{item.item_type}:{item.item_id}" for item in results[:3]
        )
        return (
            f"I found {len(results)} options that fit your request. "
            f"Top picks: {preview_items}."
        )

    def _clarification_response(
        self,
        *,
        session_state: SessionState,
        assistant_message: str,
    ) -> OrchestratorResponse:
        next_state = session_state.model_copy(deep=True)
        next_state.status = "explore"
        next_state.last_message_at = datetime.now(timezone.utc)
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=assistant_message,
            recommendations=[],
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )

    def _safe_error_response(
        self,
        *,
        session_state: SessionState,
        assistant_message: str,
    ) -> OrchestratorResponse:
        next_state = session_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=assistant_message,
            recommendations=[],
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )
