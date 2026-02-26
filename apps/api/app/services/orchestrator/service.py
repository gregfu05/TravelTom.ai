"""LLM-first orchestration service with deterministic recommendation guarantees."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError

from app.schemas.state import SessionState
from app.schemas.tools.recommendations import (
    RecommendationConstraints,
    RecommendationQuery,
    RecommendationResult,
    RecommendationToolResponse,
)
from app.services.orchestrator.extraction import (
    apply_message_state_updates,
    apply_structured_state_patch,
    extract_query_filters,
)
from app.services.orchestrator.langchain_compat import (
    LANGCHAIN_AVAILABLE,
    create_runnable_lambda,
    create_structured_tool,
    normalize_structured_payload,
)
from app.services.orchestrator.policies import (
    LLMComposedResponse,
    LLMOrchestrationPlan,
    OrchestratorPolicyConfig,
    RecommendationQueryControls,
    build_clarification_message,
    build_planning_prompt_context,
    build_response_prompt_context,
)
from app.services.orchestrator.schemas import OrchestratorResponse

RecommendationTool = Callable[
    [RecommendationQuery],
    RecommendationToolResponse | dict[str, Any],
]
StructuredModel = Callable[[dict[str, Any]], dict[str, Any] | BaseModel | str]

_VALID_ITEM_TYPES = {"destination", "hotel", "flight"}


def placeholder_recommendation_tool(
    query: RecommendationQuery,
) -> RecommendationToolResponse:
    """Temporary recommendation tool used until recommender integration is ready."""

    return RecommendationToolResponse(
        results=[],
        ranking_version=query.ranking_version,
    )


class OrchestratorService:
    """Coordinate LLM planning/composition and deterministic tool execution."""

    def __init__(
        self,
        recommendation_tool: RecommendationTool | None = None,
        policy_config: OrchestratorPolicyConfig | None = None,
        planning_model: StructuredModel | None = None,
        response_model: StructuredModel | None = None,
    ) -> None:
        self._recommendation_handler = (
            recommendation_tool or placeholder_recommendation_tool
        )
        self._policy = policy_config or OrchestratorPolicyConfig()
        self._planning_model = planning_model or self._default_planning_model
        self._response_model = response_model or self._default_response_model
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
        self._planning_chain = create_runnable_lambda(self._invoke_planning_chain)
        self._response_chain = create_runnable_lambda(self._invoke_response_chain)

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
        """Run LLM-first orchestration for a single user message."""

        message = user_message.strip()
        if not message:
            return self._clarification_response(
                session_state=session_state,
                assistant_message=(
                    "Tell me where and when you want to travel, plus your budget, "
                    "and I can suggest options."
                ),
            )

        plan, planned_state = self._resolve_plan(
            user_message=message,
            session_state=session_state,
        )
        if not plan.should_call_recommendation_tool:
            clarification_message = (
                plan.clarification_message or build_clarification_message(planned_state)
            )
            return self._clarification_response(
                session_state=planned_state,
                assistant_message=clarification_message,
            )

        query = self._build_recommendation_query(
            user_message=message,
            session_state=planned_state,
            query_controls=plan.query_controls,
        )
        if query is None:
            return self._safe_error_response(
                session_state=planned_state,
                assistant_message=(
                    "I could not validate your request yet. Please share destination, "
                    "dates, and budget so I can continue."
                ),
            )

        try:
            recommendation_response = self._recommendation_chain.invoke(query)
        except FuturesTimeoutError:
            return self._safe_error_response(
                session_state=planned_state,
                assistant_message=(
                    "I could not finish the recommendation lookup in time. "
                    "Please try again in a moment."
                ),
            )
        except ValidationError:
            return self._safe_error_response(
                session_state=planned_state,
                assistant_message=(
                    "I received an invalid recommendation payload. Please retry and "
                    "I will fetch results again."
                ),
            )
        except Exception:
            return self._safe_error_response(
                session_state=planned_state,
                assistant_message=(
                    "I hit a temporary tool error. Please retry and I will continue "
                    "from this plan."
                ),
            )

        next_state = planned_state.model_copy(deep=True)
        next_state.last_message_at = datetime.now(timezone.utc)
        next_state.last_recommendation_version = recommendation_response.ranking_version

        if not recommendation_response.results:
            next_state.status = "explore"
            fallback_message = (
                "I do not have strong matches yet. "
                f"{build_clarification_message(next_state)}"
            )
            assistant_message = self._compose_assistant_message(
                session_state=next_state,
                user_message=message,
                recommendations=[],
                fallback_message=fallback_message,
                outcome="empty_results",
            )
            return OrchestratorResponse(
                session_id=next_state.session_id,
                assistant_message=assistant_message,
                recommendations=[],
                itinerary=next_state.itinerary.model_dump(),
                state=next_state.model_dump(mode="json"),
            )

        next_state.status = "refine"
        fallback_message = self._build_results_message(recommendation_response.results)
        assistant_message = self._compose_assistant_message(
            session_state=next_state,
            user_message=message,
            recommendations=recommendation_response.results,
            fallback_message=fallback_message,
            outcome="results",
        )
        return OrchestratorResponse(
            session_id=next_state.session_id,
            assistant_message=assistant_message,
            recommendations=recommendation_response.results,
            itinerary=next_state.itinerary.model_dump(),
            state=next_state.model_dump(mode="json"),
        )

    def _resolve_plan(
        self,
        *,
        user_message: str,
        session_state: SessionState,
    ) -> tuple[LLMOrchestrationPlan, SessionState]:
        fallback_plan = LLMOrchestrationPlan.from_guardrail(
            message=user_message,
            session_state=session_state,
            max_results=self._policy.max_recommendation_results,
        )
        try:
            llm_plan = self._planning_chain.invoke(
                {
                    "user_message": user_message,
                    "session_state": session_state,
                    "max_results": self._policy.max_recommendation_results,
                }
            )
        except (ValidationError, TypeError):
            llm_plan = fallback_plan
        except Exception:
            llm_plan = fallback_plan

        state_patch = llm_plan.state_patch.model_dump(mode="python", exclude_none=True)
        try:
            patched_state = apply_structured_state_patch(
                session_state=session_state,
                state_patch=state_patch,
            )
        except ValidationError:
            patched_state = session_state.model_copy(deep=True)

        # Deterministic extraction remains as a guardrail when LLM misses fields.
        extracted_state = apply_message_state_updates(
            message=user_message,
            session_state=patched_state,
        )
        return llm_plan, extracted_state

    def _build_recommendation_query(
        self,
        *,
        user_message: str,
        session_state: SessionState,
        query_controls: RecommendationQueryControls,
    ) -> RecommendationQuery | None:
        normalized_query = query_controls.query or user_message
        filters = self._merge_query_filters(
            user_message=user_message,
            llm_filters=query_controls.filters,
        )
        payload: dict[str, Any] = {
            "session_id": session_state.session_id,
            "query": normalized_query,
            "constraints": self._build_constraints_payload(session_state),
            "filters": filters,
            "max_results": query_controls.max_results
            or self._policy.max_recommendation_results,
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

    def _merge_query_filters(
        self,
        *,
        user_message: str,
        llm_filters: dict[str, Any],
    ) -> dict[str, str]:
        llm_item_type = self._normalize_item_type(llm_filters.get("item_type"))
        guardrail_item_type = extract_query_filters(user_message).get("item_type")
        selected_item_type = llm_item_type or guardrail_item_type
        if selected_item_type is None:
            return {}
        return {"item_type": selected_item_type}

    def _normalize_item_type(self, item_type: Any) -> str | None:
        if not isinstance(item_type, str):
            return None
        normalized = item_type.strip().casefold()
        if normalized.endswith("s"):
            normalized = normalized[:-1]
        if normalized in _VALID_ITEM_TYPES:
            return normalized
        return None

    def _compose_assistant_message(
        self,
        *,
        session_state: SessionState,
        user_message: str,
        recommendations: list[RecommendationResult],
        fallback_message: str,
        outcome: Literal["results", "empty_results"],
    ) -> str:
        try:
            composed = self._response_chain.invoke(
                {
                    "session_state": session_state,
                    "user_message": user_message,
                    "recommendations": recommendations,
                    "fallback_message": fallback_message,
                    "outcome": outcome,
                }
            )
        except (ValidationError, TypeError):
            return fallback_message
        except Exception:
            return fallback_message
        return composed.assistant_message

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

    def _invoke_planning_chain(self, payload: dict[str, Any]) -> LLMOrchestrationPlan:
        prompt_context = build_planning_prompt_context(
            session_state=payload["session_state"],
            user_message=payload["user_message"],
            max_results=payload["max_results"],
        )
        model_output = self._planning_model(
            {
                "prompt": prompt_context,
                "session_state": payload["session_state"],
                "user_message": payload["user_message"],
                "max_results": payload["max_results"],
            }
        )
        if isinstance(model_output, str):
            raise TypeError("Planning model must return structured JSON output")
        normalized_payload = normalize_structured_payload(model_output)
        return LLMOrchestrationPlan.model_validate(normalized_payload)

    def _invoke_response_chain(self, payload: dict[str, Any]) -> LLMComposedResponse:
        prompt_context = build_response_prompt_context(
            session_state=payload["session_state"],
            user_message=payload["user_message"],
            recommendations=payload["recommendations"],
            fallback_message=payload["fallback_message"],
            outcome=payload["outcome"],
        )
        model_output = self._response_model(
            {
                "prompt": prompt_context,
                "session_state": payload["session_state"],
                "user_message": payload["user_message"],
                "recommendations": payload["recommendations"],
                "fallback_message": payload["fallback_message"],
                "outcome": payload["outcome"],
            }
        )
        if isinstance(model_output, str):
            return LLMComposedResponse(assistant_message=model_output)
        normalized_payload = normalize_structured_payload(model_output)
        return LLMComposedResponse.model_validate(normalized_payload)

    def _default_planning_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_state = payload["session_state"]
        user_message = str(payload["user_message"])
        max_results = int(payload["max_results"])

        guardrail_plan = LLMOrchestrationPlan.from_guardrail(
            message=user_message,
            session_state=session_state,
            max_results=max_results,
        ).model_dump(mode="python")
        guardrail_plan["query_controls"]["filters"] = extract_query_filters(
            user_message
        )
        return guardrail_plan

    def _default_response_model(self, payload: dict[str, Any]) -> dict[str, str]:
        return {"assistant_message": str(payload["fallback_message"])}

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
